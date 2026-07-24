# Budget failures state the exact pre-call invariant that failed.
# ruff: noqa: TRY003

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.v2.models import ContextManifest, StructuredSummaryRevision

BASELINE_TOKENS = 40_000


class ContextOverflowError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BudgetRequest:
    provider_kind: str
    context_window: int
    output_tokens: int
    configured_cap: int | None = None
    tool_schema: dict[str, Any] | None = None
    safety_tokens: int = 1_000


@dataclass(frozen=True, slots=True)
class ContextBudget:
    total: int
    reserved: dict[str, int]
    categories: dict[str, int]


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    source_id: str
    node_id: str
    extract: str
    priority: int
    contradiction: bool = False


@dataclass(frozen=True, slots=True)
class BuiltContext:
    instructions: str
    selected: tuple[EvidenceItem, ...]
    token_estimates: dict[str, int]


def estimate_tokens(value: str | dict[str, Any], provider_kind: str = "OPENAI") -> int:
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value, sort_keys=True, separators=(",", ":"))
    )
    divisor = 3.5 if provider_kind == "GEMINI" else 4
    return max(1, int(len(text) / divisor) + 1)


class ContextBudgetAllocator:
    def extraction_character_budget(
        self, context_window: int, provider_kind: str = "OPENAI"
    ) -> int:
        budget = self.allocate(
            BudgetRequest(
                provider_kind=provider_kind,
                context_window=context_window,
                configured_cap=context_window,
                output_tokens=4_000,
            )
        )
        return max(4_000, budget.categories["evidence"] * 4)

    def allocate(self, request: BudgetRequest) -> ContextBudget:
        desired = (
            request.configured_cap
            if request.configured_cap is not None
            else BASELINE_TOKENS
        )
        total = min(request.context_window, desired)
        tool_tokens = (
            estimate_tokens(request.tool_schema, request.provider_kind)
            if request.tool_schema
            else 0
        )
        reserved = {
            "output": request.output_tokens,
            "tools": tool_tokens,
            "safety": request.safety_tokens,
        }
        available = total - sum(reserved.values())
        if available <= 0:
            raise ContextOverflowError("reserves exceed effective context window")
        base_extra = max(0, total - BASELINE_TOKENS)
        instructions = min(6_000, int(available * 0.18))
        state = min(5_000, int(available * 0.14))
        contradictions = min(6_000 + int(base_extra * 0.25), int(available * 0.25))
        evidence = available - instructions - state - contradictions
        return ContextBudget(
            total=total,
            reserved=reserved,
            categories={
                "instructions": instructions,
                "state": state,
                "contradictions": contradictions,
                "evidence": evidence,
            },
        )

    def build(
        self,
        request: BudgetRequest,
        *,
        instructions: str,
        evidence: tuple[EvidenceItem, ...],
        unresolved_min_tokens: int = 0,
    ) -> BuiltContext:
        budget = self.allocate(request)
        instruction_tokens = estimate_tokens(instructions, request.provider_kind)
        if instruction_tokens > budget.categories["instructions"]:
            # Deterministic compaction keeps the beginning and ending constraints.
            character_limit = budget.categories["instructions"] * 4
            instructions = (
                instructions[: character_limit // 2]
                + instructions[-character_limit // 2 :]
            )
            instruction_tokens = estimate_tokens(instructions, request.provider_kind)
        if (
            unresolved_min_tokens
            > budget.categories["evidence"] + budget.categories["contradictions"]
        ):
            raise ContextOverflowError(
                "unresolved evidence cannot fit before provider call"
            )
        selected: list[EvidenceItem] = []
        used = 0
        limit = budget.categories["evidence"] + budget.categories["contradictions"]
        for item in sorted(
            evidence,
            key=lambda value: (-value.contradiction, value.priority, value.evidence_id),
        ):
            tokens = estimate_tokens(item.extract, request.provider_kind)
            if used + tokens <= limit:
                selected.append(item)
                used += tokens
        return BuiltContext(
            instructions=instructions,
            selected=tuple(selected),
            token_estimates={"instructions": instruction_tokens, "evidence": used},
        )


def _safe_summary(summary: Any) -> Any:
    forbidden = {"transcript", "raw_body", "chain_of_thought", "reasoning"}
    if isinstance(summary, dict):
        return {
            key: _safe_summary(value)
            for key, value in summary.items()
            if key.lower() not in forbidden
        }
    if isinstance(summary, list):
        return [_safe_summary(value) for value in summary]
    return summary


def persist_context_revision(
    session,
    *,
    run_id: str | None,
    selected: tuple[EvidenceItem, ...],
    token_estimates: dict[str, int],
    summary: dict[str, Any],
) -> ContextManifest:
    manifest = ContextManifest(
        id=f"ctx-{uuid4().hex}",
        run_id=run_id,
        manifest_json={
            "evidence_ids": [item.evidence_id for item in selected],
            "source_ids": sorted({item.source_id for item in selected}),
            "node_ids": sorted({item.node_id for item in selected}),
            "token_estimates": dict(token_estimates),
        },
    )
    session.add(manifest)
    session.flush()
    session.add(
        StructuredSummaryRevision(
            id=f"summary-{uuid4().hex}",
            manifest_id=manifest.id,
            revision_number=1,
            summary_json=_safe_summary(summary),
        )
    )
    return manifest
