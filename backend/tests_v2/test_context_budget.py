# ruff: noqa: ARG002, TRY003

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.context import (
    BudgetRequest,
    ContextBudgetAllocator,
    ContextOverflowError,
    EvidenceItem,
    estimate_tokens,
    persist_context_revision,
)
from app.v2.contracts import PlannerOutput
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.gateway import StructuredModelGateway
from app.v2.models import ContextManifest, StructuredSummaryRevision
from app.v2.providers import ModelResponse, Usage


@pytest.mark.unit
def test_budget_baseline_and_large_window_scale_evidence_mainly() -> None:
    allocator = ContextBudgetAllocator()
    base = allocator.allocate(
        BudgetRequest(
            provider_kind="OPENAI",
            context_window=40_000,
            output_tokens=4_000,
            tool_schema={"type": "object"},
        )
    )
    large = allocator.allocate(
        BudgetRequest(
            provider_kind="GEMINI",
            context_window=100_000,
            configured_cap=80_000,
            output_tokens=4_000,
            tool_schema={"type": "object"},
        )
    )
    assert base.total == 40_000
    assert large.total == 80_000
    assert (
        large.categories["evidence"] - base.categories["evidence"]
        > large.categories["instructions"] - base.categories["instructions"]
    )
    assert large.categories["contradictions"] > base.categories["contradictions"]
    assert allocator.extraction_character_budget(
        40_000, "OPENAI"
    ) < allocator.extraction_character_budget(80_000, "OPENAI")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_overflow_fails_deterministically_before_provider_call(
    isolated_paths,
) -> None:
    class Router:
        calls = 0

        async def complete(self, task, request, requirements):
            self.calls += 1
            raise AssertionError("provider must not be called")

    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    router = Router()
    evidence = tuple(
        EvidenceItem(f"e{i}", "s", "n", "x" * 10_000, priority=i) for i in range(10)
    )
    with pytest.raises(ContextOverflowError):
        await StructuredModelGateway(engine, router).call(
            run_id=None,
            task="research.plan",
            role_prompt="plan",
            payload={"evidence_ids": [item.evidence_id for item in evidence]},
            output_type=PlannerOutput,
            evidence=evidence,
            context_window=4_000,
        )
    assert router.calls == 0


@pytest.mark.integration
def test_manifest_and_summary_persist_ids_without_transcript_or_raw_body(
    isolated_paths,
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        manifest = persist_context_revision(
            session,
            run_id=None,
            selected=(EvidenceItem("e1", "s1", "n1", "compact", priority=1),),
            token_estimates={"evidence": 5},
            summary={
                "facts": ["fact"],
                "transcript": "must disappear",
                "raw_body": "must disappear",
            },
        )
        manifest_id = manifest.id
    with Session(engine) as session:
        stored = session.get(ContextManifest, manifest_id)
        summary = session.scalar(select(StructuredSummaryRevision))
        serialized = str(stored.manifest_json) + str(summary.summary_json)
        assert stored.manifest_json["evidence_ids"] == ["e1"]
        assert stored.manifest_json["source_ids"] == ["s1"]
        assert stored.manifest_json["node_ids"] == ["n1"]
        assert "transcript" not in serialized
        assert "raw_body" not in serialized


@pytest.mark.integration
def test_summary_scrubs_nested_reasoning_fields(isolated_paths) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        persist_context_revision(
            session,
            run_id=None,
            selected=(),
            token_estimates={},
            summary={"sections": [{"fact": "safe", "chain_of_thought": "private"}]},
        )
    with Session(engine) as session:
        summary = session.scalar(select(StructuredSummaryRevision))
        assert summary.summary_json == {"sections": [{"fact": "safe"}]}


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_gateway_accounts_for_entire_serialized_request(isolated_paths) -> None:
    class Router:
        request = None
        requirements = None

        async def complete(self, task, request, requirements):
            self.request = request
            self.requirements = requirements
            return ModelResponse(
                text='{"questions":[{"id":"q","domain":"d","question":"q","queries":["x"],"required_indicators":["i"],"source_budget":1,"stop_conditions":["s"]}]}',
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    router = Router()
    await StructuredModelGateway(engine, router).call(
        run_id=None,
        task="research.plan",
        role_prompt="planner/v1: safe",
        payload={"nested": "x" * 1000},
        output_type=PlannerOutput,
        context_window=40_000,
    )
    serialized = router.request.model_dump(mode="json")
    assert router.requirements.input_tokens >= estimate_tokens(serialized)
    assert (
        router.requirements.input_tokens + router.requirements.output_tokens + 1_000
        <= 40_000
    )
