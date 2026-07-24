from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.v2.bootstrap import BUILTIN_POLICIES
from app.v2.contracts import (
    AuditDecision,
    AuditVerdict,
    CreateResearchRun,
    ResearchRunTargetInput,
    ResearchScope,
)
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.domain import GraphCycleError
from app.v2.models import (
    CanonNode,
    CanonNodeRevision,
    ClaimConflict,
    MaterialProposalFieldRecord,
    MaterialProposalRecord,
    RelationshipAssertion,
    RelationshipRevision,
    ResearchWorkspace,
    Source,
    SourceRevision,
    World,
)
from app.v2.projections import ResearchQueryService
from app.v2.research_runs import ResearchRunKernel
from app.v2.workflow import (
    CompletionInputs,
    EvidenceEligibilityError,
    evaluate_completion,
    independent_support_count,
    policy_obligations,
    validate_evidence_eligibility,
    validate_promotion_source_policy,
    validate_relationship_graph,
)


@pytest.fixture
def engine(isolated_paths: dict[str, Path]) -> Engine:
    value = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(value)
    with Session(value) as session, session.begin():
        session.add_all(
            [
                World(id="w1", name="One", franchise="F", category="SF"),
                World(id="w2", name="Two", franchise="F", category="SF"),
            ]
        )
    return value


def scope(continuity: str = "prime") -> ResearchScope:
    return ResearchScope(
        world_id="w1",
        subject_ids=("subject",),
        continuity=continuity,
        era_or_timepoint="era-1",
        conditions=("prototype",),
    )


@pytest.mark.unit
def test_evidence_policy_rejects_contradiction_as_support_and_wrong_scope() -> None:
    target = scope()
    evidence = {
        "supports": {
            "support_role": "SUPPORTS",
            "world_id": "w1",
            "subject_ids": ["subject"],
            "continuity": "prime",
            "era_or_timepoint": "era-1",
            "branch_id": "main",
            "conditions": ["prototype"],
            "domain": "mechanisms",
        },
        "contradicts": {
            "support_role": "CONTRADICTS",
            "world_id": "w1",
            "subject_ids": ["subject"],
            "continuity": "prime",
            "era_or_timepoint": "era-1",
            "branch_id": "main",
            "conditions": ["prototype"],
            "domain": "mechanisms",
        },
    }
    validate_evidence_eligibility(target, "mechanisms", ("supports",), (), evidence)
    with pytest.raises(EvidenceEligibilityError, match="eligible support"):
        validate_evidence_eligibility(
            target, "mechanisms", ("contradicts",), (), evidence
        )
    evidence["supports"]["continuity"] = "alternate"
    with pytest.raises(EvidenceEligibilityError, match="continuity"):
        validate_evidence_eligibility(target, "mechanisms", ("supports",), (), evidence)
    with pytest.raises(EvidenceEligibilityError, match="unknown"):
        validate_evidence_eligibility(target, "mechanisms", ("missing",), (), evidence)
    evidence["supports"]["continuity"] = "prime"
    evidence["supports"]["branch_id"] = "alternate"
    with pytest.raises(EvidenceEligibilityError, match="branch"):
        validate_evidence_eligibility(target, "mechanisms", ("supports",), (), evidence)
    evidence["supports"]["branch_id"] = "main"
    evidence["supports"]["conditions"] = ["production"]
    with pytest.raises(EvidenceEligibilityError, match="conditions"):
        validate_evidence_eligibility(target, "mechanisms", ("supports",), (), evidence)


@pytest.mark.unit
def test_qualifies_is_support_only_when_policy_preserves_limitation() -> None:
    evidence = {
        "qualified": {
            "support_role": "QUALIFIES",
            "world_id": "w1",
            "subject_ids": ["subject"],
            "continuity": "prime",
            "era_or_timepoint": "era-1",
            "branch_id": "main",
            "conditions": ["prototype"],
            "domain": "mechanisms",
        }
    }
    validate_evidence_eligibility(
        scope(),
        "mechanisms",
        ("qualified",),
        (),
        evidence,
        field_name="qualifier",
        field_value="prototype",
    )
    with pytest.raises(EvidenceEligibilityError, match="qualifier"):
        validate_evidence_eligibility(
            scope(),
            "mechanisms",
            ("qualified",),
            (),
            evidence,
            field_name="effect",
            field_value="bends spacetime",
        )


@pytest.mark.integration
@pytest.mark.evaluation
def test_same_name_in_separate_continuities_has_no_latest_revision_loss(
    engine: Engine,
) -> None:
    with Session(engine) as session, session.begin():
        session.add(CanonNode(id="node", world_id="w1", kind="MECHANISM"))
        session.add_all(
            [
                CanonNodeRevision(
                    id="prime-rev",
                    node_id="node",
                    revision_number=1,
                    fields_json={"name": "Engine", "effect": "prime"},
                    scope_json=scope("prime").model_dump(mode="json"),
                ),
                CanonNodeRevision(
                    id="alt-rev",
                    node_id="node",
                    revision_number=2,
                    fields_json={"name": "Engine", "effect": "alternate"},
                    scope_json=scope("alternate").model_dump(mode="json"),
                ),
            ]
        )
    service = ResearchQueryService(engine)
    assert (
        service.accepted_graph("w1", continuity="prime")[0]["revision_id"]
        == "prime-rev"
    )
    assert (
        service.accepted_graph("w1", continuity="alternate")[0]["revision_id"]
        == "alt-rev"
    )


@pytest.mark.integration
def test_unrelated_world_conflict_isolated_by_workspace(engine: Engine) -> None:
    kernel = ResearchRunKernel(engine)
    run1 = kernel.create(
        CreateResearchRun(
            objective="one",
            scope={},
            targets=(ResearchRunTargetInput(world_id="w1", objective="one"),),
        ),
        "isolation-1",
    )
    run2 = kernel.create(
        CreateResearchRun(
            objective="two",
            scope={},
            targets=(ResearchRunTargetInput(world_id="w2", objective="two"),),
        ),
        "isolation-2",
    )
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                ResearchWorkspace(
                    id="ws1",
                    run_id=run1.id,
                    target_id=run1.targets[0].id,
                    world_id="w1",
                    continuity="prime",
                    brief_json={},
                    status="ACTIVE",
                ),
                ResearchWorkspace(
                    id="ws2",
                    run_id=run2.id,
                    target_id=run2.targets[0].id,
                    world_id="w2",
                    continuity="prime",
                    brief_json={},
                    status="ACTIVE",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                MaterialProposalRecord(
                    id="p1",
                    workspace_id="ws1",
                    kind="MECHANISM",
                    scope_json={},
                    fields_json={"x": 1},
                ),
                MaterialProposalRecord(
                    id="p2",
                    workspace_id="ws2",
                    kind="MECHANISM",
                    scope_json={},
                    fields_json={"x": 2},
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                MaterialProposalFieldRecord(
                    id="f1", proposal_id="p1", name="x", value_json=1
                ),
                MaterialProposalFieldRecord(
                    id="f2", proposal_id="p2", name="x", value_json=2
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ClaimConflict(
                    id="c1", proposal_field_id="f1", workspace_id="ws1", status="OPEN"
                ),
                ClaimConflict(
                    id="c2", proposal_field_id="f2", workspace_id="ws2", status="OPEN"
                ),
            ]
        )
    assert [
        item["id"]
        for item in ResearchQueryService(engine).gaps_conflicts("ws1")["conflicts"]
    ] == ["c1"]


@pytest.mark.unit
def test_relationship_audit_is_unique_and_cycle_is_rejected() -> None:
    accepted = AuditDecision(
        assertion_type="RELATIONSHIP",
        assertion_id="rel-1",
        proposal_id="rel-1",
        field_name="relationship",
        verdict=AuditVerdict.ACCEPT,
        reason_code="EXACT_SUPPORT",
        evidence_fragment_ids=("e1",),
        policy_version="audit.v1",
        model_call_id="call-1",
        manifest_id=None,
    )
    with pytest.raises(GraphCycleError):
        validate_relationship_graph(
            (("a", "b", "IS_A"), ("b", "a", "IS_A")),
            {"rel-1": accepted},
        )


@pytest.mark.unit
def test_completion_policy_requires_all_thresholds_and_domains() -> None:
    complete = CompletionInputs(
        required_indicators=frozenset({"a", "b", "c", "d", "e"}),
        accepted_indicators=frozenset({"a", "b", "c", "d", "e"}),
        critical_questions=frozenset({"q1", "q2"}),
        accepted_questions=frozenset({"q1", "q2"}),
        allowed_gap_questions=frozenset(),
        provenance_rate=1.0,
        domain_coverage={"mechanisms": 0.8, "limits": 0.6},
        unresolved_invalidating_conflicts=0,
        unresolved_audit_decisions=0,
        duplicate_promotions=0,
    )
    assert evaluate_completion(complete).outcome.value == "COMPLETE"
    partial = evaluate_completion(
        replace(complete, domain_coverage={"mechanisms": 1.0, "limits": 0.4})
    )
    assert partial.outcome.value == "PARTIAL"
    assert "DOMAIN_COVERAGE_BELOW_0.60:limits" in partial.reasons


@pytest.mark.unit
def test_builtin_research_policy_defines_material_domain_obligations() -> None:
    policy = next(
        item for item in BUILTIN_POLICIES if item.policy_type == "RESEARCH_COMPLETION"
    )
    domains = policy.definition_json["domains"]
    assert set(domains) == {
        "identity_scope",
        "mechanisms_capabilities",
        "energy_resources",
        "industry_logistics",
        "mobility",
        "offense",
        "defense",
        "information_control",
        "biology",
        "exotic",
        "deployment_scale",
        "chronology",
        "counters_limits",
    }
    assert all(value["required_indicators"] for value in domains.values())
    assert all(value["critical_questions"] for value in domains.values())
    assert policy.definition_json["overall_threshold"] == 0.8
    assert policy.definition_json["domain_threshold"] == 0.6


@pytest.mark.unit
def test_empty_domain_selection_expands_to_full_policy_catalog() -> None:
    obligations = policy_obligations(())
    assert set(obligations) == {
        "identity_scope",
        "mechanisms_capabilities",
        "energy_resources",
        "industry_logistics",
        "mobility",
        "offense",
        "defense",
        "information_control",
        "biology",
        "exotic",
        "deployment_scale",
        "chronology",
        "counters_limits",
    }


@pytest.mark.unit
def test_builtin_canon_policy_versions_high_impact_source_requirements() -> None:
    policy = next(item for item in BUILTIN_POLICIES if item.policy_type == "CANON")
    assert policy.id == "canon.default.v1"
    assert set(policy.definition_json["high_impact_fields"]) >= {
        "quantity",
        "yield",
        "range",
        "speed",
        "offense",
        "defense",
        "deployment_scale",
    }
    assert policy.definition_json["promotion_sources"] == {
        "eligible_classes": [
            "PRIMARY",
            "OFFICIAL",
            "LICENSED",
            "SECONDARY",
            "MIRROR",
        ],
        "high_impact_min_independent": 2,
    }


@pytest.mark.unit
def test_policy_obligations_cannot_be_omitted_by_planner() -> None:
    obligations = policy_obligations(("mechanisms", "offense"))
    assert obligations["mechanisms"]["policy_domain"] == "mechanisms_capabilities"
    assert set(obligations["mechanisms"]["required_indicators"]) == {
        "effect",
        "activation",
        "limits",
    }
    assert "delivery" in obligations["offense"]["required_indicators"]


@pytest.mark.unit
def test_pre_gate_profile_tables_are_absent() -> None:
    from app.v2.models import Base

    assert "power_profile" not in Base.metadata.tables
    assert "profile_condition" not in Base.metadata.tables


@pytest.mark.integration
def test_source_metadata_and_mirror_lineage_are_reproducible(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                Source(
                    id="s1",
                    canonical_url="https://one",
                    source_class="PRIMARY",
                    publisher="Pub",
                    lineage_id="original",
                ),
                Source(
                    id="s2",
                    canonical_url="https://mirror",
                    source_class="MIRROR",
                    publisher="Mirror",
                    lineage_id="original",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                SourceRevision(
                    id="r1",
                    source_id="s1",
                    content_hash="a" * 64,
                    extractor_name="html",
                    extractor_version="1",
                ),
                SourceRevision(
                    id="r2",
                    source_id="s2",
                    content_hash="a" * 64,
                    extractor_name="html",
                    extractor_version="1",
                ),
            ]
        )
    with Session(engine) as session:
        rows = session.scalars(
            select(SourceRevision).where(SourceRevision.content_hash == "a" * 64)
        ).all()
        assert len({session.get(Source, row.source_id).lineage_id for row in rows}) == 1
        assert independent_support_count(session, ("r1", "r2")) == 1


@pytest.mark.unit
def test_source_policy_rejects_unknown_and_requires_independent_support() -> None:
    with pytest.raises(EvidenceEligibilityError, match="ineligible source"):
        validate_promotion_source_policy(
            ({"source_class": "UNKNOWN", "lineage_id": "a"},), high_impact=False
        )
    with pytest.raises(EvidenceEligibilityError, match="independent"):
        validate_promotion_source_policy(
            (
                {"source_class": "PRIMARY", "lineage_id": "same"},
                {"source_class": "SECONDARY", "lineage_id": "same"},
            ),
            high_impact=True,
        )
    validate_promotion_source_policy(
        (
            {"source_class": "PRIMARY", "lineage_id": "one"},
            {"source_class": "SECONDARY", "lineage_id": "two"},
        ),
        high_impact=True,
    )


@pytest.mark.integration
@pytest.mark.evaluation
def test_effective_knowledge_preserves_inherited_field_origin_revision(
    engine: Engine,
) -> None:
    scoped = scope().model_dump(mode="json")
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                CanonNode(id="parent", world_id="w1", kind="MODEL"),
                CanonNode(id="child", world_id="w1", kind="INSTANCE"),
            ]
        )
        session.flush()
        session.add_all(
            [
                CanonNodeRevision(
                    id="parent-rev",
                    node_id="parent",
                    revision_number=1,
                    fields_json={"effect": "inherited"},
                    scope_json=scoped,
                ),
                CanonNodeRevision(
                    id="child-rev",
                    node_id="child",
                    revision_number=1,
                    fields_json={"name": "Child"},
                    scope_json=scoped,
                ),
            ]
        )
        session.add(
            RelationshipAssertion(
                id="inherits", source_node_id="child", target_node_id="parent"
            )
        )
        session.flush()
        session.add(
            RelationshipRevision(
                id="inherits-rev",
                assertion_id="inherits",
                revision_number=1,
                relation_type="INSTANCE_OF",
                scope_json=scoped,
            )
        )
    child = next(
        item
        for item in ResearchQueryService(engine).effective_knowledge(
            "w1", continuity="prime", timepoint="era-1"
        )
        if item["node_id"] == "child"
    )
    assert child["field_origins"]["effect"] == {
        "node_id": "parent",
        "node_revision_id": "parent-rev",
    }
    assert child["field_origins"]["name"] == {
        "node_id": "child",
        "node_revision_id": "child-rev",
    }
