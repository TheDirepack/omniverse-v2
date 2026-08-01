# Stable gateway diagnostics and compact repair prompts intentionally exceed lint rules.
# ruff: noqa: E501, SIM105, TRY003

from __future__ import annotations

import hashlib
import inspect
import json
from time import monotonic
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
from app.v2.logging import redact
from app.v2.models import ModelCall
from app.v2.providers import ModelRequest
from app.v2.routing import RoutingRequirements

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(ValueError):
    pass


class StructuredModelGateway:
    def __init__(
        self,
        engine,
        router,
        allocator: ContextBudgetAllocator | None = None,
        *,
        logger=None,
    ) -> None:
        self.engine = engine
        self.router = router
        self.allocator = allocator or ContextBudgetAllocator()
        self.logger = logger

    def _log(
        self, event_type: str, message: str, *, level="INFO", data=None, **correlation
    ) -> None:
        if self.logger is None:
            return
        try:
            self.logger.log_agent(
                "model-gateway",
                event_type,
                message=message,
                level=level,
                data=redact(
                    {
                        **{
                            name: correlation[name]
                            for name in ("attempt_number", "step_kind")
                            if correlation.get(name) is not None
                        },
                        **(data or {}),
                    }
                ),
                **correlation,
            )
        except Exception:
            pass

    async def call(
        self,
        *,
        run_id: str | None,
        target_id: str | None = None,
        world_id: str | None = None,
        attempt_number: int | None = None,
        step_kind: str | None = None,
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
        prompt_version = role_prompt.split(":", 1)[0]
        correlation = {
            "run_id": run_id,
            "target_id": target_id,
            "step_id": step_id,
            "world_id": world_id,
            "attempt_number": attempt_number,
            "step_kind": step_kind,
        }
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
        base_data = {
            "task": task,
            "prompt_version": prompt_version,
            "schema_version": output_type.__name__,
            "prompt_sha256": hashlib.sha256(role_prompt.encode()).hexdigest(),
            "schema_sha256": hashlib.sha256(
                json.dumps(schema, sort_keys=True).encode()
            ).hexdigest(),
            "payload": payload,
            "selected_evidence_count": len(selected),
            "request_tokens": request_tokens,
            "output_tokens_budget": output_tokens,
            "context_window": context_window,
        }
        self._log(
            "model.context.built",
            "Model context built",
            data=base_data,
            **correlation,
        )
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
            call_data = {**base_data, "call_attempt": attempt + 1}
            self._log(
                "model.call.started",
                "Model call started",
                data=call_data,
                **correlation,
            )
            started = monotonic()
            try:
                complete = self.router.complete
                parameters = inspect.signature(complete).parameters
                route_correlation = {
                    key: value
                    for key, value in correlation.items()
                    if value is not None
                }
                if (
                    any(
                        parameter.kind is inspect.Parameter.VAR_KEYWORD
                        for parameter in parameters.values()
                    )
                    or "run_id" in parameters
                ):
                    response = await complete(
                        task,
                        request,
                        RoutingRequirements(
                            structured=True,
                            input_tokens=request_tokens,
                            output_tokens=output_tokens,
                        ),
                        **route_correlation,
                    )
                else:
                    response = await complete(
                        task,
                        request,
                        RoutingRequirements(
                            structured=True,
                            input_tokens=request_tokens,
                            output_tokens=output_tokens,
                        ),
                    )
            except Exception as error:
                self._log(
                    "model.call.failed",
                    "Model call failed",
                    level="ERROR",
                    data={
                        **call_data,
                        "duration_ms": (monotonic() - started) * 1000,
                        "error_class": type(error).__name__,
                        "error_message": str(error),
                    },
                    **correlation,
                )
                raise
            response_data = {
                **call_data,
                "duration_ms": (monotonic() - started) * 1000,
                "usage": response.usage.model_dump(mode="json"),
                "finish_reason": response.finish_reason,
                "response_id": response.response_id,
                "provider_id": response.provider_id,
                "model_id": response.model_id,
            }
            self._log(
                "model.call.succeeded",
                "Model call succeeded",
                data=response_data,
                model_id=response.model_id,
                provider_id=response.provider_id,
                **correlation,
            )
            self._log(
                "model.text.returned",
                "Provider returned model text",
                data={**response_data, "text": response.text},
                **correlation,
            )
            if response.returned_reasoning is not None:
                self._log(
                    "model.reasoning.returned",
                    "Provider returned explicit reasoning content",
                    data={
                        **response_data,
                        "reasoning": response.returned_reasoning,
                        "reasoning_field": response.reasoning_field,
                    },
                    **correlation,
                )
            for tool_call in response.tool_calls:
                self._log(
                    "model.tool_call.returned",
                    "Provider returned a tool call",
                    data={
                        **response_data,
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    },
                    **correlation,
                )
            try:
                result = output_type.model_validate_json(response.text, strict=True)
            except (json.JSONDecodeError, ValidationError, TypeError) as error:
                self._log(
                    "model.output.validation_failed",
                    "Structured model output failed validation",
                    level="WARNING",
                    data={**response_data, "error_class": type(error).__name__},
                    **correlation,
                )
                if attempt:
                    self._log(
                        "model.repair.failed",
                        "Structured output repair failed",
                        level="ERROR",
                        data={**response_data, "error_class": type(error).__name__},
                        **correlation,
                    )
                    raise StructuredOutputError(
                        f"invalid structured output for {task}"
                    ) from error
                self._log(
                    "model.repair.started",
                    "Structured output repair started",
                    data=response_data,
                    **correlation,
                )
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
            self._log(
                "model.output.validated",
                "Structured model output validated",
                data={**response_data, "output": result.model_dump(mode="json")},
                **correlation,
            )
            if attempt:
                self._log(
                    "model.repair.succeeded",
                    "Structured output repair succeeded",
                    data=response_data,
                    **correlation,
                )
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
                        "prompt_version": prompt_version,
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
                            prompt_version=prompt_version,
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
