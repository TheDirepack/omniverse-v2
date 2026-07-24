# Stable gateway diagnostics and compact repair prompts intentionally exceed lint rules.
# ruff: noqa: E501, TRY003

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.v2.context import (
    BudgetRequest,
    ContextBudgetAllocator,
    ContextOverflowError,
    EvidenceItem,
    estimate_tokens,
    persist_context_revision,
)
from app.v2.models import ModelCall
from app.v2.providers import ModelRequest
from app.v2.routing import RoutingRequirements

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(ValueError):
    pass


class StructuredModelGateway:
    def __init__(
        self, engine, router, allocator: ContextBudgetAllocator | None = None
    ) -> None:
        self.engine = engine
        self.router = router
        self.allocator = allocator or ContextBudgetAllocator()

    async def call(
        self,
        *,
        run_id: str | None,
        task: str,
        role_prompt: str,
        payload: dict[str, object],
        output_type: type[T],
        evidence: tuple[EvidenceItem, ...] = (),
        context_window: int = 40_000,
        output_tokens: int = 4_000,
        model_call_id: str | None = None,
        step_id: str | None = None,
    ) -> T:
        schema = output_type.model_json_schema()
        built = self.allocator.build(
            BudgetRequest(
                provider_kind="OPENAI",
                context_window=context_window,
                configured_cap=context_window,
                output_tokens=output_tokens,
                tool_schema=schema,
            ),
            instructions=role_prompt,
            evidence=evidence,
        )
        selected = list(built.selected)
        while True:
            context = {
                "task": payload,
                "evidence": [
                    {"fragment_id": item.evidence_id, "exact_excerpt": item.extract}
                    for item in selected
                ],
            }
            messages = (
                {"role": "system", "content": built.instructions},
                {"role": "user", "content": json.dumps(context, sort_keys=True)},
            )
            request = ModelRequest(
                model="routed",
                messages=messages,
                max_output_tokens=output_tokens,
                structured_schema=schema,
            )
            request_tokens = estimate_tokens(request.model_dump(mode="json"))
            if request_tokens + output_tokens + 1_000 <= context_window:
                break
            if not selected:
                raise ContextOverflowError(
                    "serialized request exceeds effective context window"
                )
            selected.pop()
        for attempt in range(2):
            request = ModelRequest(
                model="routed",
                messages=messages,
                max_output_tokens=output_tokens,
                structured_schema=schema,
            )
            request_tokens = estimate_tokens(request.model_dump(mode="json"))
            if request_tokens + output_tokens + 1_000 > context_window:
                raise ContextOverflowError(
                    "serialized request exceeds effective context window"
                )
            response = await self.router.complete(
                task,
                request,
                RoutingRequirements(
                    structured=True,
                    input_tokens=request_tokens,
                    output_tokens=output_tokens,
                ),
            )
            try:
                result = output_type.model_validate_json(response.text, strict=True)
            except (json.JSONDecodeError, ValidationError, TypeError) as error:
                if attempt:
                    raise StructuredOutputError(
                        f"invalid structured output for {task}"
                    ) from error
                messages = (
                    *messages,
                    {"role": "assistant", "content": response.text},
                    {
                        "role": "user",
                        "content": "Return one JSON object matching the supplied schema. No prose.",
                    },
                )
                repaired_tokens = sum(
                    estimate_tokens(message["content"]) for message in messages
                )
                if repaired_tokens + output_tokens + 1_000 > context_window:
                    raise ContextOverflowError(
                        "malformed-output repair context exceeds context window"
                    ) from error
                continue
            with Session(self.engine) as session, session.begin():
                manifest = persist_context_revision(
                    session,
                    run_id=run_id,
                    selected=tuple(selected),
                    token_estimates={
                        **built.token_estimates,
                        "evidence": sum(
                            estimate_tokens(item.extract) for item in selected
                        ),
                        "payload": estimate_tokens(payload),
                        "schema": estimate_tokens(schema),
                        "output": output_tokens,
                        "safety": 1_000,
                        "request_total": request_tokens + output_tokens + 1_000,
                        "effective_limit": context_window,
                    },
                    summary={
                        "task": task,
                        "prompt_version": role_prompt.split(":", 1)[0],
                        "schema_version": output_type.__name__,
                        "usage": response.usage.model_dump(mode="json"),
                        "finish_reason": response.finish_reason,
                    },
                )
                if model_call_id is not None and step_id is not None:
                    session.add(
                        ModelCall(
                            id=model_call_id,
                            step_id=step_id,
                            task=task,
                            prompt_version=role_prompt.split(":", 1)[0],
                            schema_version=output_type.__name__,
                            selected_evidence_ids_json=[
                                item.evidence_id for item in selected
                            ],
                            usage_json=response.usage.model_dump(mode="json"),
                            provider_id=response.provider_id,
                            model_id=response.model_id,
                            response_id=response.response_id,
                            response_json=result.model_dump(mode="json"),
                            manifest_id=manifest.id,
                        )
                    )
            return result
        raise AssertionError("unreachable")
