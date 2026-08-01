from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.contracts import (
    AuditDecision,
    AuditVerdict,
    CanonNodeContract,
    CanonNodeKind,
    CreateResearchRun,
    CursorPage,
    ErrorEnvelope,
    EvidenceFragmentContract,
    MaterialProposal,
    MaterialProposalField,
    MechanismContract,
    MechanismModality,
    PlannerOutput,
    PlanQuestion,
    ProviderCredentialInput,
    ProviderCredentialOutput,
    RelationshipContract,
    ResearchBrief,
    ResearchDepth,
    ResearchGap,
    ResearchOutcome,
    ResearchOutcomeStatus,
    ResearchPlan,
    ResearchRunTargetInput,
    ResearchScope,
    RunTargetProjection,
    SourceRevisionContract,
    TimelineBranchContract,
    TimelineEventContract,
    TimelineScope,
)


def scope() -> ResearchScope:
    return ResearchScope(
        world_id="bt",
        subject_ids=("atlas",),
        continuity="classic",
        era_or_timepoint="3025",
        conditions=("operational",),
    )


@pytest.mark.unit
def test_research_run_accepts_empty_focus_and_inherits_global_targeting() -> None:
    command = CreateResearchRun(
        objective="   ",
        scope={"continuity": "Prime"},
        keywords=["  Atlas  ", "atlas", "Heat sinks"],
        phrases=(" exact phrase ", "EXACT PHRASE", "second phrase"),
        section_hints=["Capabilities, Limits", " capabilities, limits ", "History"],
        targets=[{"world_id": "bt"}],
    )

    assert command.objective == ""
    assert command.keywords == ("Atlas", "Heat sinks")
    assert command.phrases == ("exact phrase", "second phrase")
    assert command.section_hints == ("Capabilities, Limits", "History")
    assert command.targets[0].model_dump() == {"world_id": "bt"}
    assert command.targets[0].objective == ""
    assert command.targets[0].scope == {
        "continuity": "Prime",
        "keywords": ["Atlas", "Heat sinks"],
        "phrases": ["exact phrase", "second phrase"],
        "section_hints": ["Capabilities, Limits", "History"],
    }


@pytest.mark.unit
def test_research_run_target_and_projection_remove_legacy_public_fields() -> None:
    assert set(ResearchRunTargetInput.model_fields) == {"world_id"}
    assert "objective" not in RunTargetProjection.model_fields
    assert "scope" not in RunTargetProjection.model_fields
    with pytest.raises(ValidationError):
        ResearchRunTargetInput(world_id="bt", objective="legacy")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        CreateResearchRun(
            scope={"domains": ["mechanisms"]},
            targets=({"world_id": "bt"},),
        )


@pytest.mark.unit
def test_planner_evidence_and_gap_contracts_are_domain_free() -> None:
    question = PlanQuestion(
        id="q-identity",
        priority=1,
        question="Who is Atlas?",
        queries=("Atlas identity",),
        source_budget=2,
        stop_conditions=("official identity source found",),
    )
    assert PlannerOutput(questions=(question,)).model_dump() == {
        "questions": (
            {
                "id": "q-identity",
                "priority": 1,
                "question": "Who is Atlas?",
                "queries": ("Atlas identity",),
                "source_budget": 2,
                "stop_conditions": ("official identity source found",),
            },
        )
    }
    assert "domain" not in PlanQuestion.model_fields
    assert "required_indicators" not in PlanQuestion.model_fields
    assert "domain" not in EvidenceFragmentContract.model_fields
    assert "domain" not in ResearchGap.model_fields
    assert "missing_indicator" not in ResearchGap.model_fields


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("keywords", [f"keyword-{index}" for index in range(51)]),
        ("keywords", ["x" * 101]),
        ("phrases", [f"phrase-{index}" for index in range(31)]),
        ("phrases", ["x" * 301]),
        ("section_hints", [f"section-{index}" for index in range(31)]),
        ("section_hints", ["x" * 201]),
    ],
)
def test_research_targeting_limits(field: str, values: list[str]) -> None:
    with pytest.raises(ValidationError):
        CreateResearchRun(**{field: values, "targets": [{"world_id": "bt"}]})

    with pytest.raises(ValidationError):
        CreateResearchRun(objective="x" * 2001, targets=[{"world_id": "bt"}])


@pytest.mark.unit
def test_scope_is_strict_frozen_and_rejects_unknown_fields() -> None:
    value = scope()
    with pytest.raises(ValidationError):
        value.world_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ResearchScope(
            world_id="bt",
            subject_ids=("atlas",),
            continuity="classic",
            era_or_timepoint="3025",
            conditions=(),
            surprise=True,  # type: ignore[call-arg]
        )


@pytest.mark.unit
def test_material_proposals_require_supported_kind_scope_and_evidence() -> None:
    with pytest.raises(ValidationError):
        MaterialProposal(
            proposal_id="p1",
            kind="theory",  # type: ignore[arg-type]
            scope=scope(),
            fields={"effect": "destroys armor"},
            evidence_fragment_ids=("e1",),
        )
    with pytest.raises(ValidationError):
        MaterialProposal(
            proposal_id="p1",
            kind=CanonNodeKind.MECHANISM,
            scope=scope(),
            fields={"effect": "destroys armor"},
            evidence_fragment_ids=(),
        )
    field = MaterialProposalField(
        name="effect",
        value="destroys armor",
        supporting_fragment_ids=("e1",),
        contradicting_fragment_ids=(),
    )
    assert field.supporting_fragment_ids == ("e1",)
    with pytest.raises(ValidationError):
        MaterialProposalField(
            name="effect",
            value="unsupported",
            supporting_fragment_ids=(),
            contradicting_fragment_ids=(),
        )


@pytest.mark.unit
def test_relationship_contract_requires_scope_and_evidence() -> None:
    relation = RelationshipContract(
        assertion_id="r1",
        relation_type="IMPLEMENTS",
        source_node_id="model",
        target_node_id="mechanism",
        scope=scope(),
        evidence_fragment_ids=("e1",),
        valid_from="3025",
        valid_to=None,
    )
    assert relation.scope.world_id == "bt"
    with pytest.raises(ValidationError):
        RelationshipContract(**(relation.model_dump() | {"evidence_fragment_ids": ()}))


@pytest.mark.unit
def test_phase_one_contract_catalog_is_strict_and_secret_safe() -> None:
    brief = ResearchBrief(
        brief_id="b1",
        scope=scope(),
        canon_policy_id="canon.default.v1",
        objective="Document engine behavior",
        requested_domains=("energy",),
        exclusions=(),
        depth=ResearchDepth.STANDARD,
        source_budget=10,
        model_budget=3,
        completion_policy_id="research.default.v1",
    )
    ResearchPlan(
        plan_id="plan1",
        brief_id=brief.brief_id,
        questions=("How is heat generated?",),
        source_priorities=("primary",),
        stop_conditions=("budget_exhausted",),
        explicit_unknowns=("exact output",),
    )
    ResearchGap(
        gap_id="g1",
        scope=scope(),
        question_id="q-output",
        question="Exact output?",
        attempted_leads=(),
        next_query="official engine rating",
        priority=1,
        stop_reason=None,
    )
    for status in ResearchOutcomeStatus:
        ResearchOutcome(
            status=status, accepted_proposal_ids=(), gap_ids=(), conflict_ids=()
        )

    revision = SourceRevisionContract(
        revision_id="sr1",
        source_id="s1",
        content_hash="a" * 64,
        retrieved_at="2026-01-01T00:00:00Z",
    )
    EvidenceFragmentContract(
        fragment_id="e1",
        source_revision_id=revision.revision_id,
        locator="p. 3",
        exact_excerpt="quoted",
        normalized_statement="statement",
        subject_ids=("atlas",),
        continuity="classic",
        temporal_scope=TimelineScope(
            valid_from="3025", valid_to=None, branch_id="main"
        ),
        support_role="SUPPORTS",
        extraction_confidence=0.9,
    )
    AuditDecision(
        assertion_type="FIELD",
        assertion_id="p1:effect",
        proposal_id="p1",
        field_name="effect",
        verdict=AuditVerdict.ACCEPT,
        reason_code="DIRECT_SUPPORT",
        evidence_fragment_ids=("e1",),
        policy_version="audit.v1",
        model_call_id="call-1",
        manifest_id=None,
    )
    CanonNodeContract(node_id="n1", kind=CanonNodeKind.MECHANISM, world_id="bt")
    TimelineBranchContract(
        branch_id="main", world_id="bt", parent_branch_id=None, divergence_point=None
    )
    MechanismContract(
        node_id="fusion",
        modality=MechanismModality.TECHNOLOGICAL,
        effect="generates power",
        targets=("reactor",),
        activation="startup",
        costs=("fuel",),
        duration="continuous",
        control="regulated",
        reliability="high",
        dependencies=("fuel",),
        limits=("heat",),
        counters=("damage",),
        temporal_semantics=None,
        causal_semantics=None,
    )
    TimelineEventContract(
        node_id="event1",
        scope=TimelineScope(valid_from="3025", valid_to="3025", branch_id="main"),
        participant_node_ids=("atlas",),
        affected_relationship_ids=(),
        relative_to_event_ids=(),
        disputed=False,
        looping=False,
    )

    assert {
        MechanismModality.MAGICAL,
        MechanismModality.REALITY_ALTERING,
        MechanismModality.TEMPORAL,
        MechanismModality.CAUSAL,
        MechanismModality.CONCEPTUAL,
        MechanismModality.ONTOLOGICAL,
    }.issubset(set(MechanismModality))

    credential = ProviderCredentialInput(
        provider_id="openai", label="primary", secret="sk-secret"
    )
    output = ProviderCredentialOutput(
        credential_id="c1", provider_id=credential.provider_id, label="primary"
    )
    assert "secret" not in output.model_dump()
    assert "sk-secret" not in output.model_dump_json()
    ErrorEnvelope(code="INVALID", message="bad input", details={}, request_id="req1")
    CursorPage[str](items=("one",), next_cursor="opaque")
