# Injected fakes intentionally ignore protocol arguments.
# ruff: noqa: ARG002, E501, TRY003

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.v2.blobs import BlobStore
from app.v2.contracts import (
    CreateResearchRun,
    PlannerOutput,
    ResearchRunTargetInput,
)
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.domain import StepKind
from app.v2.gateway import StructuredModelGateway, StructuredOutputError
from app.v2.models import (
    CanonNode,
    CanonNodeRevision,
    ClaimConflict,
    ContextManifest,
    EvidenceFragment,
    IntegrationEffect,
    ModelCall,
    ModelStepEffect,
    NodeEvidence,
    ResearchGapRecord,
    Source,
    SourceRevision,
    StepEffect,
    World,
)
from app.v2.projections import ResearchQueryService
from app.v2.providers import ModelResponse, Usage
from app.v2.research_runs import ResearchRunKernel
from app.v2.workflow import (
    ResearchWorkflow,
    _resolve_fragment_id,
    _scoped_model_id,
)


class FakeRouter:
    def __init__(self, responses: dict[str, list[dict[str, object]]]) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.requests = []

    async def complete(self, task, request, requirements):
        self.calls.append(task)
        self.requests.append(request)
        value = self.responses[task].pop(0)
        if task == "research.summary":
            mapping = json.loads(request.messages[-1]["content"])["task"][
                "accepted_facts"
            ][0]
            value["facts"][0]["node_id"] = mapping["node_id"]
            value["facts"][0]["node_revision_id"] = mapping["node_revision_id"]
        return ModelResponse(
            text=json.dumps(value),
            tool_calls=(),
            usage=Usage(input_tokens=10, output_tokens=10, total_tokens=20),
        )


class FailingRouter(FakeRouter):
    async def complete(self, task, request, requirements):
        self.calls.append(task)
        raise RuntimeError("provider exploded")


class FakeSearch:
    async def search(self, query: str, *, limit: int):
        return (
            {
                "url": "https://example.test/fusion",
                "title": "Fusion engine",
                "snippet": "A lead, not evidence",
                "rank": 1,
            },
        )


class EmptySearch:
    async def search(self, query: str, *, limit: int):
        return ()


class FakeAcquisition:
    def __init__(self, engine: Engine, blobs: BlobStore) -> None:
        self.engine = engine
        self.blobs = blobs
        self.calls = 0

    async def acquire(
        self,
        url,
        policy,
        *,
        force_refresh=False,
        idempotency_key,
        attempt_id=None,
        step_id=None,
        source_class="SECONDARY",
        publisher=None,
        lineage_id=None,
    ):
        from app.v2.acquisition import AcquisitionResult
        from app.v2.models import Source

        self.calls += 1
        body = b"The prototype fusion engine bends local spacetime."
        blob_hash = self.blobs.put(body)
        with Session(self.engine) as session, session.begin():
            source = session.get(Source, "source-fusion")
            if source is None:
                session.add(
                    Source(
                        id="source-fusion",
                        canonical_url=url,
                        source_class=source_class,
                        publisher=publisher,
                        lineage_id=lineage_id,
                    )
                )
                session.flush()
            revision = session.get(SourceRevision, "revision-fusion")
            if revision is None:
                session.add(
                    SourceRevision(
                        id="revision-fusion",
                        source_id="source-fusion",
                        content_hash=blob_hash,
                        blob_hash=blob_hash,
                        content_type="text/plain",
                    )
                )
        return AcquisitionResult(
            "source-fusion",
            "revision-fusion",
            url,
            blob_hash,
            body.decode(),
            self.calls > 1,
        )


@pytest.fixture
def workflow_parts(isolated_paths: dict[str, Path]):
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        session.add(
            World(
                id="world-1",
                name="Example",
                franchise="Example",
                category="SF",
                continuity="prime",
            )
        )
        session.add(
            World(
                id="world-2",
                name="Second",
                franchise="Example",
                category="SF",
                continuity="prime",
            )
        )
    blobs = BlobStore(isolated_paths["blobs"])
    return engine, blobs


def command() -> CreateResearchRun:
    return CreateResearchRun(
        objective="Document fusion engine",
        scope={"continuity": "prime", "domains": ["mechanisms"]},
        targets=(
            ResearchRunTargetInput(
                world_id="world-1", objective="Document fusion engine"
            ),
        ),
    )


@pytest.mark.integration
def test_model_local_ids_are_scoped_without_fragment_primary_key_collisions(
    workflow_parts,
) -> None:
    engine, _ = workflow_parts
    assert _scoped_model_id("proposal", "workspace-a", "p1") != _scoped_model_id(
        "proposal", "workspace-b", "p1"
    )
    with Session(engine) as session, session.begin():
        session.add(Source(id="source-collision", canonical_url="https://example.test"))
        session.add(
            SourceRevision(
                id="revision-collision",
                source_id="source-collision",
                content_hash="0" * 64,
            )
        )
        session.flush()
        session.add(
            EvidenceFragment(
                id="f1",
                source_revision_id="revision-collision",
                locator="one",
                exact_excerpt="one",
                content_hash="a" * 64,
            )
        )
        session.flush()
        resolved = _resolve_fragment_id(session, "f1", "b" * 64)
    assert resolved != "f1"


def responses() -> dict[str, list[dict[str, object]]]:
    scope = {
        "world_id": "world-1",
        "subject_ids": ["fusion-engine"],
        "continuity": "prime",
        "era_or_timepoint": "unspecified",
        "conditions": [],
    }
    return {
        "research.plan": [
            {
                "questions": [
                    {
                        "id": "q1",
                        "domain": "mechanisms",
                        "question": "What does the fusion engine do?",
                        "queries": ["Example fusion engine mechanism"],
                        "required_indicators": ["effect", "activation", "limits"],
                        "source_budget": 1,
                        "stop_conditions": ["one primary source"],
                    }
                ]
            }
        ],
        "research.extract": [
            {
                "fragments": [
                    {
                        "fragment_id": "fragment-support",
                        "source_revision_id": "revision-fusion",
                        "locator": "chars:0-52",
                        "exact_excerpt": "The prototype fusion engine bends local spacetime.",
                        "normalized_statement": "The prototype bends local spacetime.",
                        "domain": "mechanisms",
                        "subject_ids": ["fusion-engine"],
                        "continuity": "prime",
                        "temporal_scope": {
                            "valid_from": None,
                            "valid_to": None,
                            "branch_id": "main",
                        },
                        "support_role": "SUPPORTS",
                        "extraction_confidence": 0.95,
                    },
                    {
                        "fragment_id": "fragment-qualifier",
                        "source_revision_id": "revision-fusion",
                        "locator": "chars:4-13",
                        "exact_excerpt": "prototype",
                        "normalized_statement": "The engine is a prototype.",
                        "domain": "mechanisms",
                        "subject_ids": ["fusion-engine"],
                        "continuity": "prime",
                        "temporal_scope": {
                            "valid_from": None,
                            "valid_to": None,
                            "branch_id": "main",
                        },
                        "support_role": "QUALIFIES",
                        "extraction_confidence": 0.95,
                    },
                ]
            }
        ],
        "research.synthesize": [
            {
                "proposals": [
                    {
                        "proposal_id": "proposal-fusion",
                        "kind": "MECHANISM",
                        "scope": scope,
                        "fields": {
                            "name": "Fusion engine",
                            "effect": "bends local spacetime",
                            "qualifier": "prototype",
                            "modality": "REALITY_ALTERING",
                            "activation": "prototype operation",
                            "limits": "prototype only",
                        },
                        "field_evidence": {
                            "name": {
                                "supporting": ["fragment-support"],
                                "contradicting": [],
                            },
                            "effect": {
                                "supporting": ["fragment-support"],
                                "contradicting": [],
                            },
                            "qualifier": {
                                "supporting": ["fragment-qualifier"],
                                "contradicting": [],
                            },
                            "modality": {
                                "supporting": ["fragment-support"],
                                "contradicting": [],
                            },
                            "activation": {
                                "supporting": ["fragment-support"],
                                "contradicting": [],
                            },
                            "limits": {
                                "supporting": ["fragment-support"],
                                "contradicting": [],
                            },
                        },
                    }
                ],
                "relationships": [],
            }
        ],
        "research.audit": [
            {
                "decisions": [
                    {
                        "assertion_type": "FIELD",
                        "assertion_id": f"proposal-fusion:{name}",
                        "proposal_id": "proposal-fusion",
                        "field_name": name,
                        "verdict": "ACCEPT",
                        "reason_code": "EXACT_SUPPORT",
                        "evidence_fragment_ids": [
                            (
                                "fragment-qualifier"
                                if name == "qualifier"
                                else "fragment-support"
                            )
                        ],
                        "policy_version": "audit.v1",
                        "model_call_id": "call-audit",
                        "manifest_id": None,
                    }
                    for name in (
                        "name",
                        "effect",
                        "qualifier",
                        "modality",
                        "activation",
                        "limits",
                    )
                ]
            }
        ],
        "research.summary": [
            {
                "facts": [
                    {
                        "text": "The prototype fusion engine bends local spacetime.",
                        "node_id": "ACTUAL_CANON_ID",
                        "node_revision_id": "ACTUAL_REVISION_ID",
                        "fragment_ids": ["fragment-support"],
                    }
                ]
            }
        ],
    }


@pytest.mark.asyncio
async def test_multi_target_handlers_use_each_lease_target_objective_and_scope(
    workflow_parts,
):
    engine, blobs = workflow_parts
    plan = responses()["research.plan"][0]
    router = FakeRouter({"research.plan": [plan, plan]})
    kernel = ResearchRunKernel(engine)
    run = kernel.create(
        CreateResearchRun(
            objective="run objective",
            scope={"continuity": "wrong-default", "domains": ["wrong"]},
            targets=(
                ResearchRunTargetInput(
                    world_id="world-1",
                    objective="objective one",
                    scope={"continuity": "prime", "domains": ["mechanisms"]},
                ),
                ResearchRunTargetInput(
                    world_id="world-2",
                    objective="objective two",
                    scope={"continuity": "prime", "domains": ["mechanisms"]},
                ),
            ),
        ),
        "multi-target-context",
    )
    workflow = ResearchWorkflow(
        engine, kernel, router, FakeSearch(), FakeAcquisition(engine, blobs)
    )
    for _ in range(4):
        assert await workflow.run_next(run.id)
    plan_payloads = [
        json.loads(request.messages[-1]["content"])["task"]
        for request in router.requests
    ]
    assert {
        (payload["inventory"]["world"]["id"], payload["objective"])
        for payload in plan_payloads
    } == {
        ("world-1", "objective one"),
        ("world-2", "objective two"),
    }


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
async def test_simple_complete_research_is_durable_and_repeat_safe(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "workflow-one")
    router = FakeRouter(responses())
    acquisition = FakeAcquisition(engine, blobs)
    workflow = ResearchWorkflow(engine, kernel, router, FakeSearch(), acquisition)

    while await workflow.run_next(run.id):
        pass
    result = kernel.get(run.id)
    assert result.outcome.value == "COMPLETE", [
        (step.kind.value, step.error) for step in result.steps if step.error
    ]
    assert router.calls == [
        "research.plan",
        "research.extract",
        "research.synthesize",
        "research.audit",
        "research.summary",
    ]
    audit_request = router.requests[router.calls.index("research.audit")]
    audit_request_context = json.loads(audit_request.messages[-1]["content"])
    audit_context = audit_request_context["task"]
    assert audit_context["canon_policy"]["id"] == "canon.default.v1"
    assert audit_context["evidence"][0]["source_class"] == "SECONDARY"
    assert audit_request_context["evidence"][0]["exact_excerpt"]
    assert "support_role" in audit_context["evidence"][0]
    assert "qualifiers" in audit_context
    assert "contradiction_set" in audit_context
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CanonNode)) == 1
        assert session.scalar(select(func.count()).select_from(EvidenceFragment)) == 2
        assert session.scalar(select(func.count()).select_from(ModelStepEffect)) == 5
        calls = session.scalars(select(ModelCall)).all()
        assert len(calls) == 5
        assert all(
            call.manifest_id and call.prompt_version and call.schema_version
            for call in calls
        )
        assert all(call.selected_evidence_ids_json is not None for call in calls)
        assert all(call.usage_json["total_tokens"] == 20 for call in calls)
        evidence_calls = {
            call.task: set(call.selected_evidence_ids_json)
            for call in calls
            if call.task
            in {"research.synthesize", "research.audit", "research.summary"}
        }
        assert all(
            selected == {"fragment-support", "fragment-qualifier"}
            for selected in evidence_calls.values()
        )
        assert session.scalar(select(func.count()).select_from(StepEffect)) == 1
        manifests = session.scalars(select(ContextManifest)).all()
        assert all(
            {
                "instructions",
                "evidence",
                "payload",
                "schema",
                "output",
                "safety",
                "request_total",
                "effective_limit",
            }
            <= set(manifest.manifest_json["token_estimates"])
            for manifest in manifests
        )

    restarted = ResearchWorkflow(
        engine, ResearchRunKernel(engine), router, FakeSearch(), acquisition
    )
    repeated = await restarted.run(run.id)
    assert repeated.outcome.value == "COMPLETE"
    assert acquisition.calls == 1

    with Session(engine) as session:
        counts_before = {
            model: session.scalar(select(func.count()).select_from(model))
            for model in (CanonNode, SourceRevision, EvidenceFragment)
        }
    second = kernel.create(command(), "workflow-two-prior-coverage")
    second_router = FakeRouter({})
    second_result = await ResearchWorkflow(
        engine, kernel, second_router, FakeSearch(), acquisition
    ).run(second.id)
    assert second_result.outcome.value == "COMPLETE"
    assert second_router.calls == []
    assert acquisition.calls == 1
    with Session(engine) as session:
        assert counts_before == {
            model: session.scalar(select(func.count()).select_from(model))
            for model in (CanonNode, SourceRevision, EvidenceFragment)
        }


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
async def test_completion_rejects_accepted_proposal_without_persisted_integration(
    workflow_parts,
) -> None:
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "missing-integration-completion")
    workflow = ResearchWorkflow(
        engine,
        kernel,
        FakeRouter(responses()),
        FakeSearch(),
        FakeAcquisition(engine, blobs),
        max_gap_loops=0,
    )
    await workflow.run(run.id, stop_after=StepKind.INTEGRATE)
    with Session(engine) as session:
        integration_state = session.scalar(
            select(StepEffect).where(StepEffect.effect_type == "INTEGRATE")
        ).effect_json
        persisted_ids = set(session.scalars(select(IntegrationEffect.proposal_id)))
    assert integration_state["accepted_record_ids"] == list(persisted_ids)
    assert (
        integration_state["accepted_record_ids"]
        != integration_state["accepted_proposal_ids"]
    )
    result = await workflow.run(run.id)
    assert result.outcome.value == "COMPLETE", [
        (step.kind.value, step.error) for step in result.steps if step.error
    ]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
async def test_shared_engine_model_variants_and_instance_inherit_exact_origins(
    workflow_parts,
):
    engine, blobs = workflow_parts
    values = responses()
    scope = values["research.synthesize"][0]["proposals"][0]["scope"]
    definitions = [
        (
            "generic",
            "GENERIC_CONCEPT",
            {
                "name": "Fusion",
                "effect": "bends local spacetime",
                "activation": "on",
                "limits": "prototype",
            },
        ),
        ("engine", "MODEL", {"name": "Fusion Mk I", "control": "manual"}),
        ("mech-a", "MODEL", {"name": "Mech A", "variant": "assault"}),
        ("mech-b", "MODEL", {"name": "Mech B", "variant": "scout"}),
        ("instance", "INSTANCE", {"name": "Mech A 01", "control": "autonomous"}),
    ]
    proposals = []
    decisions = []
    for proposal_id, kind, fields in definitions:
        proposals.append(
            {
                "proposal_id": proposal_id,
                "kind": kind,
                "scope": scope,
                "fields": fields,
                "field_evidence": {
                    name: {
                        "supporting": ["fragment-support"],
                        "contradicting": [],
                    }
                    for name in fields
                },
            }
        )
        decisions.extend(
            {
                "assertion_type": "FIELD",
                "assertion_id": f"{proposal_id}:{name}",
                "proposal_id": proposal_id,
                "field_name": name,
                "verdict": "ACCEPT",
                "reason_code": "EXACT_SUPPORT",
                "evidence_fragment_ids": ["fragment-support"],
                "policy_version": "audit.v1",
                "model_call_id": None,
                "manifest_id": None,
            }
            for name in fields
        )
    relations = [
        ("engine-generic", "engine", "generic"),
        ("a-engine", "mech-a", "engine"),
        ("b-engine", "mech-b", "engine"),
        ("instance-a", "instance", "mech-a"),
    ]
    values["research.synthesize"][0] = {
        "proposals": proposals,
        "relationships": [
            {
                "relationship_id": relation_id,
                "relation_type": "INSTANCE_OF",
                "source_proposal_id": source,
                "target_proposal_id": target,
                "scope": scope,
                "evidence_fragment_ids": ["fragment-support"],
            }
            for relation_id, source, target in relations
        ],
    }
    decisions.extend(
        {
            "assertion_type": "RELATIONSHIP",
            "assertion_id": relation_id,
            "proposal_id": source,
            "field_name": "relationship",
            "verdict": "ACCEPT",
            "reason_code": "EXACT_SUPPORT",
            "evidence_fragment_ids": ["fragment-support"],
            "policy_version": "audit.v1",
            "model_call_id": None,
            "manifest_id": None,
        }
        for relation_id, source, _target in relations
    )
    values["research.audit"][0] = {"decisions": decisions}
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "complex-inheritance")
    result = await ResearchWorkflow(
        engine, kernel, FakeRouter(values), FakeSearch(), FakeAcquisition(engine, blobs)
    ).run(run.id)
    assert result.outcome.value == "COMPLETE"
    effective = ResearchQueryService(engine).effective_knowledge(
        "world-1", continuity="prime", timepoint="unspecified"
    )
    by_name = {item["fields"]["name"]: item for item in effective}
    instance = by_name["Mech A 01"]
    assert instance["fields"]["effect"] == "bends local spacetime"
    assert instance["fields"]["control"] == "autonomous"
    assert (
        instance["field_origins"]["effect"]
        == by_name["Fusion"]["field_origins"]["effect"]
    )
    assert instance["field_origins"]["control"]["node_id"] == instance["node_id"]
    assert by_name["Mech A"]["fields"]["control"] == "manual"
    assert by_name["Mech B"]["fields"]["control"] == "manual"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
async def test_exotic_mechanism_requires_and_promotes_all_policy_fields(
    workflow_parts,
):
    engine, blobs = workflow_parts
    values = responses()
    required = [
        "modality",
        "effect",
        "activation",
        "cost",
        "control",
        "reliability",
        "limits",
        "counters",
        "causal_temporal_rules",
    ]
    values["research.plan"][0]["questions"][0].update(
        {"domain": "exotic", "required_indicators": required}
    )
    for fragment in values["research.extract"][0]["fragments"]:
        fragment["domain"] = "exotic"
    proposal = values["research.synthesize"][0]["proposals"][0]
    proposal["fields"] = {name: f"evidenced {name}" for name in required}
    proposal["field_evidence"] = {
        name: {"supporting": ["fragment-support"], "contradicting": []}
        for name in required
    }
    values["research.audit"][0]["decisions"] = [
        {
            "assertion_type": "FIELD",
            "assertion_id": f"proposal-fusion:{name}",
            "proposal_id": "proposal-fusion",
            "field_name": name,
            "verdict": "ACCEPT",
            "reason_code": "EXACT_SUPPORT",
            "evidence_fragment_ids": ["fragment-support"],
            "policy_version": "audit.v1",
            "model_call_id": None,
            "manifest_id": None,
        }
        for name in required
    ]
    exotic = CreateResearchRun(
        objective="Document exotic mechanism",
        scope={"continuity": "prime", "domains": ["exotic"]},
        targets=(
            ResearchRunTargetInput(
                world_id="world-1", objective="Document exotic mechanism"
            ),
        ),
    )
    kernel = ResearchRunKernel(engine)
    run = kernel.create(exotic, "exotic-complete")
    result = await ResearchWorkflow(
        engine, kernel, FakeRouter(values), FakeSearch(), FakeAcquisition(engine, blobs)
    ).run(run.id)
    assert result.outcome.value == "COMPLETE"
    assert set(
        ResearchQueryService(engine).accepted_graph("world-1")[0]["fields"]
    ) == set(required)


@pytest.mark.asyncio
async def test_fabricated_excerpt_is_rejected(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "bad-excerpt")
    values = responses()
    values["research.extract"][0]["fragments"][0]["exact_excerpt"] = "Fabricated text"
    workflow = ResearchWorkflow(
        engine, kernel, FakeRouter(values), FakeSearch(), FakeAcquisition(engine, blobs)
    )
    result = await workflow.run(run.id)
    assert result.outcome.value == "FAILED"
    extract = next(step for step in result.steps if step.kind is StepKind.EXTRACT)
    assert "excerpt" in extract.error


@pytest.mark.asyncio
async def test_wrong_continuity_is_checkpointed_as_failure(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "wrong-continuity")
    values = responses()
    values["research.extract"][0]["fragments"][0]["continuity"] = "alternate"
    result = await ResearchWorkflow(
        engine, kernel, FakeRouter(values), FakeSearch(), FakeAcquisition(engine, blobs)
    ).run(run.id)
    assert result.outcome.value == "FAILED"
    extract = next(step for step in result.steps if step.kind is StepKind.EXTRACT)
    assert "continuity" in extract.error


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_open_material_contradiction_blocks_canon_promotion(workflow_parts):
    engine, blobs = workflow_parts
    values = responses()
    values["research.extract"][0]["fragments"].append(
        {
            **values["research.extract"][0]["fragments"][0],
            "fragment_id": "fragment-contradiction",
            "locator": "chars:14-26",
            "exact_excerpt": "fusion engine",
            "support_role": "CONTRADICTS",
        }
    )
    proposal = values["research.synthesize"][0]["proposals"][0]
    proposal["field_evidence"]["effect"]["contradicting"] = ["fragment-contradiction"]
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "contradiction-block")
    result = await ResearchWorkflow(
        engine,
        kernel,
        FakeRouter(values),
        FakeSearch(),
        FakeAcquisition(engine, blobs),
        max_gap_loops=0,
    ).run(run.id)
    assert result.outcome.value == "PARTIAL"
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CanonNode)) == 0


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_gateway_repairs_malformed_json_once_then_rejects(workflow_parts):
    engine, _blobs = workflow_parts

    class RawRouter:
        def __init__(self, values):
            self.values = iter(values)
            self.calls = 0

        async def complete(self, task, request, requirements):
            self.calls += 1
            return ModelResponse(
                text=next(self.values),
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    valid = json.dumps(responses()["research.plan"][0])
    repaired_router = RawRouter(["not json", valid])
    result = await StructuredModelGateway(engine, repaired_router).call(
        run_id=None,
        task="research.plan",
        role_prompt="planner/v1",
        payload={},
        output_type=PlannerOutput,
    )
    assert result.questions[0].id == "q1"
    assert repaired_router.calls == 2

    rejected_router = RawRouter(["not json", '{"questions": []} trailing'])
    with pytest.raises(StructuredOutputError):
        await StructuredModelGateway(engine, rejected_router).call(
            run_id=None,
            task="research.plan",
            role_prompt="planner/v1",
            payload={},
            output_type=PlannerOutput,
        )
    assert rejected_router.calls == 2


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
async def test_restart_after_every_step_and_provenance_traversal(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "restart-every-step")
    router = FakeRouter(responses())
    acquisition = FakeAcquisition(engine, blobs)
    for kind in StepKind:
        workflow = ResearchWorkflow(
            engine,
            ResearchRunKernel(engine),
            router,
            FakeSearch(),
            acquisition,
        )
        projection = await workflow.run(run.id, stop_after=kind)
        assert (
            next(step for step in projection.steps if step.kind is kind).status.value
            == "SUCCEEDED"
        )

    graph = ResearchQueryService(engine).accepted_graph("world-1")
    assert len(graph) == 1
    provenance = ResearchQueryService(engine).provenance(graph[0]["node_id"])
    assert {row["field_name"] for row in provenance} == {
        "name",
        "effect",
        "qualifier",
        "modality",
        "activation",
        "limits",
    }
    assert {row["fragment_id"] for row in provenance} == {
        "fragment-support",
        "fragment-qualifier",
    }


@pytest.mark.asyncio
async def test_run_next_processes_one_step_and_checkpoints_handler_exception(
    workflow_parts,
):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "one-step-failure")
    workflow = ResearchWorkflow(
        engine,
        kernel,
        FailingRouter({}),
        FakeSearch(),
        FakeAcquisition(engine, blobs),
    )
    assert await workflow.run_next(run.id)
    projection = kernel.get(run.id)
    assert projection.steps[0].status.value == "SUCCEEDED"
    assert projection.steps[1].status.value == "PENDING"
    assert await workflow.run_next(run.id)
    projection = kernel.get(run.id)
    assert projection.steps[1].status.value == "FAILED"
    assert projection.steps[1].error == "RuntimeError: provider exploded"


@pytest.mark.asyncio
async def test_cancel_request_is_observed_by_run_next_at_safe_boundary(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "run-next-cancel")
    kernel.request_cancel(
        run.id,
        (
            kernel.get(run.id).steps[0].attempts[0].started_at
            if kernel.get(run.id).steps[0].attempts
            else __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            )
        ),
    )
    workflow = ResearchWorkflow(
        engine, kernel, FakeRouter({}), FakeSearch(), FakeAcquisition(engine, blobs)
    )
    assert not await workflow.run_next(run.id)
    assert kernel.get(run.id).outcome.value == "CANCELLED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stop_after", [StepKind.PLAN, StepKind.EXTRACT, StepKind.INTEGRATE]
)
@pytest.mark.evaluation
async def test_crash_after_effect_commit_replays_without_duplicate_effect_or_model_call(
    workflow_parts, stop_after
):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), f"crash-{stop_after.value}")
    router = FakeRouter(responses())
    workflow = ResearchWorkflow(
        engine, kernel, router, FakeSearch(), FakeAcquisition(engine, blobs)
    )
    workflow.crash_after_effect_for = stop_after
    with pytest.raises(RuntimeError, match="simulated crash"):
        await workflow.run(run.id)
    calls_before = list(router.calls)
    kernel.reconcile_startup(
        workflow.clock() + __import__("datetime").timedelta(minutes=11)
    )
    workflow.crash_after_effect_for = None
    await workflow.run(run.id)
    if stop_after in {StepKind.PLAN, StepKind.EXTRACT}:
        assert router.calls.count(f"research.{stop_after.value.lower()}") == 1
    assert router.calls[: len(calls_before)] == calls_before
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CanonNode)) <= 1


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_restart_replays_validated_model_call_before_step_effect(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "crash-between-model-and-effect")
    router = FakeRouter(responses())
    workflow = ResearchWorkflow(
        engine, kernel, router, FakeSearch(), FakeAcquisition(engine, blobs)
    )
    assert await workflow.run_next(run.id)  # inventory
    workflow.crash_after_model_call_for = StepKind.PLAN
    with pytest.raises(RuntimeError, match="model call"):
        await workflow.run_next(run.id)
    with Session(engine) as session:
        call = session.scalar(
            select(ModelCall).where(ModelCall.task == "research.plan")
        )
        assert call.response_json["questions"][0]["id"] == "q1"
        assert session.scalar(select(func.count()).select_from(ModelStepEffect)) == 0
    calls_before = list(router.calls)
    kernel.reconcile_startup(
        workflow.clock() + __import__("datetime").timedelta(minutes=11)
    )
    workflow.crash_after_model_call_for = None
    assert await workflow.run_next(run.id)
    assert router.calls == calls_before
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ModelCall)) == 1
        assert session.scalar(select(func.count()).select_from(ModelStepEffect)) == 1


@pytest.mark.asyncio
async def test_summary_uses_actual_canon_node_and_revision_ids(workflow_parts):
    engine, blobs = workflow_parts
    values = responses()

    class SummaryRouter(FakeRouter):
        async def complete(self, task, request, requirements):
            if task == "research.summary":
                payload = json.loads(request.messages[-1]["content"])["task"]
                mapping = payload["accepted_facts"][0]
                self.responses[task][0]["facts"][0]["node_id"] = mapping["node_id"]
                self.responses[task][0]["facts"][0]["node_revision_id"] = mapping[
                    "node_revision_id"
                ]
            return await super().complete(task, request, requirements)

    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "actual-summary-ids")
    await ResearchWorkflow(
        engine,
        kernel,
        SummaryRouter(values),
        FakeSearch(),
        FakeAcquisition(engine, blobs),
    ).run(run.id)
    graph = ResearchQueryService(engine).accepted_graph("world-1", continuity="prime")
    fact = ResearchQueryService(engine).summary(run.id)["facts"][0]
    assert fact["node_id"] == graph[0]["node_id"]
    assert fact["node_revision_id"] == graph[0]["revision_id"]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
async def test_actionable_gap_loops_once_then_finishes_partial(workflow_parts):
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    run = kernel.create(command(), "bounded-gap-loop")
    plan = responses()["research.plan"][0]
    router = FakeRouter({"research.plan": [plan, plan]})
    result = await ResearchWorkflow(
        engine,
        kernel,
        router,
        EmptySearch(),
        FakeAcquisition(engine, blobs),
        max_gap_loops=1,
    ).run(run.id)

    assert result.outcome.value == "PARTIAL"
    assert router.calls == ["research.plan", "research.plan"]
    assert [step.kind for step in result.steps[10:]] == list(StepKind)[1:]
    gaps = ResearchQueryService(engine).gaps_conflicts(run.id)["gaps"]
    assert gaps[0]["reason"] == "INSUFFICIENT_EVIDENCE"
    assert gaps[0]["loop_cap"] == 1

    follow_up = kernel.create(command(), "follow-up-after-gap")
    follow_router = FakeRouter(responses())
    follow_result = await ResearchWorkflow(
        engine,
        kernel,
        follow_router,
        FakeSearch(),
        FakeAcquisition(engine, blobs),
    ).run(follow_up.id)
    assert follow_result.outcome.value == "COMPLETE"
    plan_payload = json.loads(follow_router.requests[0].messages[-1]["content"])["task"]
    assert plan_payload["inventory"]["gap_ids"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CanonNode)) == 1


class LargeEvidenceAcquisition(FakeAcquisition):
    def __init__(self, engine: Engine, blobs: BlobStore, body: bytes) -> None:
        super().__init__(engine, blobs)
        self.body = body

    async def acquire(self, url, policy, **kwargs):
        from app.v2.acquisition import AcquisitionResult
        from app.v2.models import Source

        self.calls += 1
        blob_hash = self.blobs.put(self.body)
        with Session(self.engine) as session, session.begin():
            if session.get(Source, "source-large") is None:
                session.add(
                    Source(
                        id="source-large",
                        canonical_url=url,
                        source_class="SECONDARY",
                        lineage_id="large-fixture",
                    )
                )
                session.flush()
            if session.get(SourceRevision, "revision-large") is None:
                session.add(
                    SourceRevision(
                        id="revision-large",
                        source_id="source-large",
                        content_hash=blob_hash,
                        blob_hash=blob_hash,
                        content_type="text/plain",
                    )
                )
        return AcquisitionResult(
            "source-large",
            "revision-large",
            url,
            blob_hash,
            self.body.decode(),
            False,
            "text/plain",
        )


class LargeEvidenceRouter:
    def __init__(self, fragments: list[dict[str, object]]) -> None:
        self.fragments = fragments
        self.requests = []

    async def complete(self, task, request, requirements):
        self.requests.append((task, request, requirements))
        scope = {
            "world_id": "world-1",
            "subject_ids": ["fusion-engine"],
            "continuity": "prime",
            "era_or_timepoint": "unspecified",
            "conditions": [],
            "branch_id": "main",
        }
        if task == "research.plan":
            value = responses()[task][0]
        elif task == "research.extract":
            value = {"fragments": self.fragments}
        elif task == "research.synthesize":
            value = responses()[task][0]
            value["proposals"][0]["scope"] = scope
            for links in value["proposals"][0]["field_evidence"].values():
                links["supporting"] = ["support-000"]
        elif task == "research.audit":
            value = responses()[task][0]
            for decision in value["decisions"]:
                decision["evidence_fragment_ids"] = ["support-000"]
        else:
            accepted = json.loads(request.messages[-1]["content"])["task"][
                "accepted_facts"
            ][0]
            value = {
                "facts": [
                    {
                        "text": self.fragments[0]["exact_excerpt"],
                        **accepted,
                        "fragment_ids": ["support-000"],
                    }
                ]
            }
        return ModelResponse(
            text=json.dumps(value),
            tool_calls=(),
            usage=Usage(input_tokens=10, output_tokens=10, total_tokens=20),
        )


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_complete_workflows_scale_relevant_and_contradictory_context(
    tmp_path: Path,
) -> None:
    results = {}
    chunk = "fusion evidence " + ("x" * 3_900)
    fragments = []
    body_parts = []
    for index in range(260):
        role = "SUPPORTS" if index % 2 == 0 else "CONTRADICTS"
        fragment_id = (
            f"{'support' if role == 'SUPPORTS' else 'contradiction'}-{index:03d}"
        )
        excerpt = f"{chunk} {fragment_id}"
        body_parts.append(excerpt)
        fragments.append(
            {
                "fragment_id": fragment_id,
                "source_revision_id": "revision-large",
                "locator": f"fixture:{index}",
                "exact_excerpt": excerpt,
                "normalized_statement": fragment_id,
                "domain": "mechanisms",
                "subject_ids": ["fusion-engine"],
                "continuity": "prime",
                "temporal_scope": {
                    "valid_from": None,
                    "valid_to": None,
                    "branch_id": "main",
                },
                "support_role": role,
                "extraction_confidence": 1.0,
            }
        )
    body = "\n".join(body_parts).encode()

    for limit in (40_000, 80_000, 200_000):
        root = tmp_path / str(limit)
        root.mkdir()
        engine = create_sqlite_engine(root / "evaluation.db")
        bootstrap_schema(engine)
        with Session(engine) as session, session.begin():
            session.add(
                World(
                    id="world-1",
                    name="Example",
                    franchise="Example",
                    category="SF",
                    continuity="prime",
                )
            )
        blobs = BlobStore(root / "blobs")
        router = LargeEvidenceRouter(fragments)
        kernel = ResearchRunKernel(engine)
        run = kernel.create(command(), f"large-context-{limit}")
        outcome = await ResearchWorkflow(
            engine,
            kernel,
            router,
            FakeSearch(),
            LargeEvidenceAcquisition(engine, blobs, body),
            context_window=limit,
        ).run(run.id)
        assert outcome.outcome.value == "COMPLETE", [
            (step.kind.value, step.error) for step in outcome.steps if step.error
        ]
        with Session(engine) as session:
            calls = session.scalars(select(ModelCall)).all()
            manifests = session.scalars(select(ContextManifest)).all()
            selected = {
                evidence_id
                for call in calls
                for evidence_id in call.selected_evidence_ids_json
            }
            serialized = json.dumps(
                [manifest.manifest_json for manifest in manifests]
                + [call.response_json for call in calls],
                sort_keys=True,
            ).lower()
            assert "raw_body" not in serialized
            assert "transcript" not in serialized
            assert "reasoning" not in serialized
            for manifest in manifests:
                tokens = manifest.manifest_json["token_estimates"]
                assert tokens["request_total"] <= tokens["effective_limit"] == limit
                assert tokens["instructions"] <= 6_000
                assert tokens["safety"] == 1_000
            results[limit] = (
                selected,
                {item for item in selected if item.startswith("contradiction-")},
                outcome.outcome.value,
            )

    selected_40, contradictions_40, outcome_40 = results[40_000]
    for limit in (80_000, 200_000):
        selected, contradictions, outcome = results[limit]
        assert len(selected) > len(selected_40)
        assert len(contradictions) > len(contradictions_40)
        assert outcome == outcome_40 == "COMPLETE"


class BranchAcquisition(FakeAcquisition):
    def __init__(self, engine, blobs, branch: str) -> None:
        super().__init__(engine, blobs)
        self.branch = branch

    async def acquire(self, url, policy, **kwargs):
        from app.v2.acquisition import AcquisitionResult
        from app.v2.models import Source

        body = f"The Relay activates the Gate during the {self.branch} event."
        blob_hash = self.blobs.put(body.encode())
        source_id = f"source-{self.branch}"
        revision_id = f"revision-{self.branch}"
        with Session(self.engine) as session, session.begin():
            if session.get(Source, source_id) is None:
                session.add(
                    Source(
                        id=source_id,
                        canonical_url=f"https://example.test/{self.branch}",
                        source_class="SECONDARY",
                        lineage_id=source_id,
                    )
                )
                session.flush()
                session.add(
                    SourceRevision(
                        id=revision_id,
                        source_id=source_id,
                        content_hash=blob_hash,
                        blob_hash=blob_hash,
                        content_type="text/plain",
                    )
                )
        return AcquisitionResult(
            source_id,
            revision_id,
            url,
            blob_hash,
            body,
            False,
            "text/plain",
        )


class BranchRouter:
    def __init__(self, branch: str) -> None:
        self.branch = branch

    async def complete(self, task, request, requirements):
        fragment_id = f"fragment-{self.branch}"
        proposal_ids = (f"mechanism-{self.branch}", f"event-{self.branch}")
        scope = {
            "world_id": "world-1",
            "subject_ids": ["relay", "gate-event"],
            "continuity": "prime",
            "era_or_timepoint": "era-1",
            "conditions": [],
            "branch_id": self.branch,
        }
        if task == "research.plan":
            value = responses()[task][0]
        elif task == "research.extract":
            excerpt = f"The Relay activates the Gate during the {self.branch} event."
            value = {
                "fragments": [
                    {
                        "fragment_id": fragment_id,
                        "source_revision_id": f"revision-{self.branch}",
                        "locator": "chars:0-80",
                        "exact_excerpt": excerpt,
                        "normalized_statement": excerpt,
                        "domain": "mechanisms",
                        "subject_ids": ["relay", "gate-event"],
                        "continuity": "prime",
                        "temporal_scope": {
                            "valid_from": "era-1",
                            "valid_to": None,
                            "branch_id": self.branch,
                        },
                        "support_role": "SUPPORTS",
                        "extraction_confidence": 1.0,
                    }
                ]
            }
        elif task == "research.synthesize":
            common = {
                "scope": scope,
                "field_evidence": {
                    name: {"supporting": [fragment_id], "contradicting": []}
                    for name in ("name", "effect", "activation", "limits")
                },
            }
            value = {
                "proposals": [
                    {
                        **common,
                        "proposal_id": proposal_ids[0],
                        "kind": "MECHANISM",
                        "fields": {
                            "name": "Relay",
                            "effect": f"opens {self.branch} Gate",
                            "activation": "event",
                            "limits": self.branch,
                        },
                    },
                    {
                        **common,
                        "proposal_id": proposal_ids[1],
                        "kind": "TIMELINE_EVENT",
                        "fields": {
                            "name": "Gate Event",
                            "effect": f"introduces {self.branch} Relay",
                            "activation": "era-1",
                            "limits": self.branch,
                        },
                    },
                ],
                "relationships": [
                    {
                        "relationship_id": f"introduces-{self.branch}",
                        "relation_type": "INTRODUCES",
                        "source_proposal_id": proposal_ids[1],
                        "target_proposal_id": proposal_ids[0],
                        "scope": scope,
                        "evidence_fragment_ids": [fragment_id],
                        "valid_from": "era-1",
                        "valid_to": None,
                    }
                ],
            }
        elif task == "research.audit":
            assertions = [
                ("FIELD", f"{proposal_id}:{field}", proposal_id, field)
                for proposal_id in proposal_ids
                for field in ("name", "effect", "activation", "limits")
            ] + [
                (
                    "RELATIONSHIP",
                    f"introduces-{self.branch}",
                    proposal_ids[1],
                    "relationship",
                )
            ]
            value = {
                "decisions": [
                    {
                        "assertion_type": assertion_type,
                        "assertion_id": assertion_id,
                        "proposal_id": proposal_id,
                        "field_name": field,
                        "verdict": "ACCEPT",
                        "reason_code": "EXACT_SUPPORT",
                        "evidence_fragment_ids": [fragment_id],
                        "policy_version": "audit.v1",
                        "model_call_id": None,
                        "manifest_id": None,
                    }
                    for assertion_type, assertion_id, proposal_id, field in assertions
                ]
            }
        else:
            mapping = json.loads(request.messages[-1]["content"])["task"][
                "accepted_facts"
            ][0]
            value = {
                "facts": [
                    {
                        "text": f"The Relay activates the Gate during the {self.branch} event.",
                        **mapping,
                        "fragment_ids": [fragment_id],
                    }
                ]
            }
        return ModelResponse(
            text=json.dumps(value),
            tool_calls=(),
            usage=Usage(input_tokens=10, output_tokens=10, total_tokens=20),
        )


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_branch_workflows_isolate_revisions_edges_and_provenance(
    workflow_parts,
) -> None:
    engine, blobs = workflow_parts
    kernel = ResearchRunKernel(engine)
    for branch in ("main", "alternate"):
        scoped = CreateResearchRun(
            objective="Document Relay timeline",
            scope={
                "continuity": "prime",
                "era_or_timepoint": "era-1",
                "branch_id": branch,
                "domains": ["mechanisms"],
            },
            targets=(
                ResearchRunTargetInput(
                    world_id="world-1", objective="Document Relay timeline"
                ),
            ),
        )
        run = kernel.create(scoped, f"branch-{branch}")
        result = await ResearchWorkflow(
            engine,
            kernel,
            BranchRouter(branch),
            FakeSearch(),
            BranchAcquisition(engine, blobs, branch),
        ).run(run.id)
        assert result.outcome.value == "COMPLETE", [
            (step.kind.value, step.error) for step in result.steps if step.error
        ]

    service = ResearchQueryService(engine)
    branch_graphs = {
        branch: service.accepted_graph(
            "world-1",
            continuity="prime",
            era_or_timepoint="era-1",
            branch_id=branch,
        )
        for branch in ("main", "alternate")
    }
    assert all(
        {node["fields"]["name"] for node in graph} == {"Relay", "Gate Event"}
        for graph in branch_graphs.values()
    )
    assert not (
        {node["revision_id"] for node in branch_graphs["main"]}
        & {node["revision_id"] for node in branch_graphs["alternate"]}
    )
    for branch, graph in branch_graphs.items():
        edges = service.relationships("world-1", continuity="prime", branch_id=branch)
        assert len(edges) == 1
        assert edges[0]["relation_type"] == "INTRODUCES"
        assert edges[0]["scope"]["branch_id"] == branch
        for node in graph:
            provenance = service.provenance(node["node_id"], branch_id=branch)
            assert provenance
            assert {row["branch_id"] for row in provenance} == {branch}


async def _deterministic_fixture(root: Path, fixture: str) -> dict[str, object]:
    await asyncio.to_thread(root.mkdir, parents=True)
    engine = create_sqlite_engine(root / "determinism.db")
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        session.add(
            World(
                id="world-1",
                name="Example",
                franchise="Example",
                category="SF",
                continuity="prime",
            )
        )
    blobs = BlobStore(root / "blobs")
    kernel = ResearchRunKernel(engine)
    outcomes = []

    async def execute(
        run_command, router, search, acquisition, key: str, *, max_gap_loops=0
    ) -> None:
        run = kernel.create(run_command, key)
        result = await ResearchWorkflow(
            engine,
            kernel,
            router,
            search,
            acquisition,
            max_gap_loops=max_gap_loops,
        ).run(run.id)
        outcomes.append(result.outcome.value)

    if fixture == "complex":
        scoped = CreateResearchRun(
            objective="Document Relay timeline",
            scope={
                "continuity": "prime",
                "era_or_timepoint": "era-1",
                "branch_id": "main",
                "domains": ["mechanisms"],
            },
            targets=(
                ResearchRunTargetInput(
                    world_id="world-1", objective="Document Relay timeline"
                ),
            ),
        )
        await execute(
            scoped,
            BranchRouter("main"),
            FakeSearch(),
            BranchAcquisition(engine, blobs, "main"),
            "complex",
        )
    elif fixture == "sparse":
        await execute(
            command(),
            FakeRouter({"research.plan": [responses()["research.plan"][0]]}),
            EmptySearch(),
            FakeAcquisition(engine, blobs),
            "sparse",
        )
    elif fixture == "contradictory":
        values = responses()
        values["research.extract"][0]["fragments"].append(
            {
                **values["research.extract"][0]["fragments"][0],
                "fragment_id": "fragment-contradiction",
                "locator": "chars:14-26",
                "exact_excerpt": "fusion engine",
                "support_role": "CONTRADICTS",
            }
        )
        values["research.synthesize"][0]["proposals"][0]["field_evidence"]["effect"][
            "contradicting"
        ] = ["fragment-contradiction"]
        await execute(
            command(),
            FakeRouter(values),
            FakeSearch(),
            FakeAcquisition(engine, blobs),
            "contradictory",
        )
    elif fixture == "multi-continuity":
        for branch in ("main", "alternate"):
            scoped = CreateResearchRun(
                objective="Document Relay timeline",
                scope={
                    "continuity": "prime",
                    "era_or_timepoint": "era-1",
                    "branch_id": branch,
                    "domains": ["mechanisms"],
                },
                targets=(
                    ResearchRunTargetInput(
                        world_id="world-1", objective="Document Relay timeline"
                    ),
                ),
            )
            await execute(
                scoped,
                BranchRouter(branch),
                FakeSearch(),
                BranchAcquisition(engine, blobs, branch),
                f"multi-{branch}",
            )
    else:
        await execute(
            command(),
            FakeRouter(responses()),
            FakeSearch(),
            FakeAcquisition(engine, blobs),
            "simple",
        )

    with Session(engine) as session:
        revisions = session.scalars(
            select(CanonNodeRevision).order_by(CanonNodeRevision.id)
        ).all()
        fragments = session.scalars(
            select(EvidenceFragment).order_by(EvidenceFragment.id)
        ).all()
        provenance = session.scalars(
            select(NodeEvidence).order_by(
                NodeEvidence.node_revision_id,
                NodeEvidence.field_name,
                NodeEvidence.evidence_fragment_id,
            )
        ).all()
        gaps = session.scalars(
            select(ResearchGapRecord).order_by(ResearchGapRecord.id)
        ).all()
        conflicts = session.scalars(
            select(ClaimConflict).order_by(ClaimConflict.id)
        ).all()
        manifests = session.scalars(
            select(ContextManifest).order_by(ContextManifest.created_at)
        ).all()
        return {
            "canon": [
                {
                    "id": revision.id,
                    "node_id": revision.node_id,
                    "fields": revision.fields_json,
                    "scope": revision.scope_json,
                }
                for revision in revisions
            ],
            "evidence": [
                {
                    "id": fragment.id,
                    "excerpt": fragment.exact_excerpt,
                    "statement": fragment.normalized_statement,
                    "role": fragment.support_role,
                    "continuity": fragment.continuity,
                    "branch": fragment.branch_id,
                }
                for fragment in fragments
            ],
            "provenance": [
                (
                    item.node_revision_id,
                    item.field_name,
                    item.evidence_fragment_id,
                )
                for item in provenance
            ],
            "gaps": [item.gap_json for item in gaps],
            "conflicts": [(item.status, item.resolution_json) for item in conflicts],
            "outcomes": sorted(outcomes),
            "context_categories": [
                manifest.manifest_json["token_estimates"] for manifest in manifests
            ],
        }


@pytest.mark.asyncio
@pytest.mark.evaluation
@pytest.mark.parametrize(
    "fixture", ["simple", "complex", "sparse", "contradictory", "multi-continuity"]
)
async def test_research_fixtures_are_exactly_deterministic(
    tmp_path: Path, fixture: str
) -> None:
    first = await _deterministic_fixture(tmp_path / fixture / "first", fixture)
    second = await _deterministic_fixture(tmp_path / fixture / "second", fixture)
    assert first == second
