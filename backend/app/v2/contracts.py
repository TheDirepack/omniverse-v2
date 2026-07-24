from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.v2.domain import RunOutcome, RunStatus, StepKind


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ResearchDepth(str, Enum):
    SURVEY = "SURVEY"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


class ResearchOutcomeStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    CONTRADICTORY = "CONTRADICTORY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    OVERFLOW = "OVERFLOW"


class CanonNodeKind(str, Enum):
    GENERIC_CONCEPT = "GENERIC_CONCEPT"
    MECHANISM = "MECHANISM"
    MODEL = "MODEL"
    INSTANCE = "INSTANCE"
    SPECIFICATION = "SPECIFICATION"
    CAPABILITY = "CAPABILITY"
    CONSTRAINT = "CONSTRAINT"
    DEPLOYMENT_FACT = "DEPLOYMENT_FACT"
    TIMELINE_EVENT = "TIMELINE_EVENT"


class MechanismModality(str, Enum):
    TECHNOLOGICAL = "TECHNOLOGICAL"
    MAGICAL = "MAGICAL"
    PSYCHIC = "PSYCHIC"
    BIOLOGICAL = "BIOLOGICAL"
    DIMENSIONAL = "DIMENSIONAL"
    REALITY_ALTERING = "REALITY_ALTERING"
    TEMPORAL = "TEMPORAL"
    CAUSAL = "CAUSAL"
    CONCEPTUAL = "CONCEPTUAL"
    ONTOLOGICAL = "ONTOLOGICAL"
    HYBRID = "HYBRID"


class AuditVerdict(str, Enum):
    ACCEPT = "ACCEPT"
    REVISE = "REVISE"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    CONTRADICTED = "CONTRADICTED"
    REJECT = "REJECT"


class ResearchScope(Contract):
    world_id: str = Field(min_length=1)
    subject_ids: tuple[str, ...] = Field(min_length=1)
    continuity: str = Field(min_length=1)
    era_or_timepoint: str = Field(min_length=1)
    conditions: tuple[str, ...]
    branch_id: str = Field(default="main", min_length=1)


class ResearchBrief(Contract):
    brief_id: str
    scope: ResearchScope
    canon_policy_id: str
    objective: str
    requested_domains: tuple[str, ...] = Field(min_length=1)
    exclusions: tuple[str, ...]
    depth: ResearchDepth
    source_budget: int = Field(gt=0)
    model_budget: int = Field(gt=0)
    completion_policy_id: str


class ResearchPlan(Contract):
    plan_id: str
    brief_id: str
    questions: tuple[str, ...] = Field(min_length=1)
    source_priorities: tuple[str, ...] = Field(min_length=1)
    stop_conditions: tuple[str, ...] = Field(min_length=1)
    explicit_unknowns: tuple[str, ...]


class PlanQuestion(Contract):
    id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    question: str = Field(min_length=1)
    queries: tuple[str, ...] = Field(min_length=1)
    required_indicators: tuple[str, ...] = Field(min_length=1)
    source_budget: int = Field(gt=0, le=100)
    stop_conditions: tuple[str, ...] = Field(min_length=1)


class PlannerOutput(Contract):
    questions: tuple[PlanQuestion, ...] = Field(min_length=1)


class ResearchGap(Contract):
    gap_id: str
    scope: ResearchScope
    domain: str
    question: str
    missing_indicator: str
    attempted_leads: tuple[str, ...]
    next_query: str | None
    priority: int = Field(ge=0)
    stop_reason: str | None


class ResearchOutcome(Contract):
    status: ResearchOutcomeStatus
    accepted_proposal_ids: tuple[str, ...]
    gap_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]


class SourceRevisionContract(Contract):
    revision_id: str
    source_id: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at: str


class TimelineScope(Contract):
    valid_from: str | None
    valid_to: str | None
    branch_id: str


class TimelineBranchContract(Contract):
    branch_id: str
    world_id: str
    parent_branch_id: str | None
    divergence_point: str | None


class EvidenceFragmentContract(Contract):
    fragment_id: str
    source_revision_id: str
    locator: str
    exact_excerpt: str
    normalized_statement: str
    domain: str
    subject_ids: tuple[str, ...] = Field(min_length=1)
    continuity: str
    temporal_scope: TimelineScope
    support_role: Literal["SUPPORTS", "CONTRADICTS", "QUALIFIES", "LEAD_ONLY"]
    extraction_confidence: float = Field(ge=0, le=1)
    conditions: tuple[str, ...] = ()


class MaterialProposal(Contract):
    proposal_id: str
    kind: CanonNodeKind
    scope: ResearchScope
    fields: dict[str, Any] = Field(min_length=1)
    evidence_fragment_ids: tuple[str, ...] = Field(min_length=1)
    contradicting_fragment_ids: tuple[str, ...] = ()


class MaterialProposalField(Contract):
    name: str
    value: Any
    supporting_fragment_ids: tuple[str, ...] = Field(min_length=1)
    contradicting_fragment_ids: tuple[str, ...]


class AuditDecision(Contract):
    assertion_type: Literal["FIELD", "RELATIONSHIP"]
    assertion_id: str
    proposal_id: str
    field_name: str
    verdict: AuditVerdict
    reason_code: str
    evidence_fragment_ids: tuple[str, ...] = Field(min_length=1)
    policy_version: str
    model_call_id: str | None
    manifest_id: str | None


class ExtractorOutput(Contract):
    fragments: tuple[EvidenceFragmentContract, ...]


class ProposalEvidence(Contract):
    supporting: tuple[str, ...] = Field(min_length=1)
    contradicting: tuple[str, ...] = ()


class StructuredProposal(Contract):
    proposal_id: str = Field(min_length=1)
    kind: CanonNodeKind
    scope: ResearchScope
    fields: dict[str, Any] = Field(min_length=1)
    field_evidence: dict[str, ProposalEvidence] = Field(min_length=1)


class StructuredRelationship(Contract):
    relationship_id: str
    relation_type: str
    source_proposal_id: str
    target_proposal_id: str
    scope: ResearchScope
    evidence_fragment_ids: tuple[str, ...] = Field(min_length=1)
    valid_from: str | None = None
    valid_to: str | None = None


class SynthesizerOutput(Contract):
    proposals: tuple[StructuredProposal, ...]
    relationships: tuple[StructuredRelationship, ...]


class AuditorOutput(Contract):
    decisions: tuple[AuditDecision, ...]


class SummaryFact(Contract):
    text: str = Field(min_length=1)
    node_id: str
    node_revision_id: str
    fragment_ids: tuple[str, ...] = Field(min_length=1)


class SummaryOutput(Contract):
    facts: tuple[SummaryFact, ...]


class CanonNodeContract(Contract):
    node_id: str
    kind: CanonNodeKind
    world_id: str


class MechanismContract(Contract):
    node_id: str
    modality: MechanismModality
    effect: str
    targets: tuple[str, ...]
    activation: str
    costs: tuple[str, ...]
    duration: str
    control: str
    reliability: str
    dependencies: tuple[str, ...]
    limits: tuple[str, ...]
    counters: tuple[str, ...]
    temporal_semantics: str | None
    causal_semantics: str | None


class TimelineEventContract(Contract):
    node_id: str
    scope: TimelineScope
    participant_node_ids: tuple[str, ...]
    affected_relationship_ids: tuple[str, ...]
    relative_to_event_ids: tuple[str, ...]
    disputed: bool
    looping: bool


class RelationshipContract(Contract):
    assertion_id: str
    relation_type: str
    source_node_id: str
    target_node_id: str
    scope: ResearchScope
    evidence_fragment_ids: tuple[str, ...] = Field(min_length=1)
    valid_from: str | None
    valid_to: str | None


class ProviderCredentialInput(Contract):
    provider_id: str
    label: str
    secret: str = Field(min_length=1, repr=False)


class ProviderCredentialOutput(Contract):
    credential_id: str
    provider_id: str
    label: str


class ErrorEnvelope(Contract):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str


T = TypeVar("T")


class CursorPage(Contract, Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None


class ResearchRunTargetInput(Contract):
    world_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    scope: dict[str, Any] = Field(default_factory=dict)


class CreateResearchRun(Contract):
    objective: str = Field(min_length=1)
    scope: dict[str, Any]
    targets: tuple[ResearchRunTargetInput, ...] = Field(min_length=1, strict=False)
    max_attempts: int = Field(default=3, ge=1, le=20)


class RunTargetProjection(Contract):
    id: str
    world_id: str
    objective: str
    scope: dict[str, Any]
    outcome: RunOutcome | None
    error: str | None


class StepAttemptProjection(Contract):
    attempt_number: int
    status: RunStatus
    owner: str
    lease_expires_at: datetime
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class RunStepProjection(Contract):
    id: str
    target_id: str
    world_id: str
    kind: StepKind
    position: int
    status: RunStatus
    attempt_count: int
    retry_due_at: datetime | None
    output_refs: tuple[str, ...]
    error: str | None
    attempts: tuple[StepAttemptProjection, ...]


class RunProjection(Contract):
    id: str
    status: RunStatus
    outcome: RunOutcome | None
    objective: str
    scope: dict[str, Any]
    cancel_requested_at: datetime | None
    targets: tuple[RunTargetProjection, ...]
    steps: tuple[RunStepProjection, ...]


class StepLease(Contract):
    step_id: str
    run_id: str
    target_id: str
    world_id: str
    kind: StepKind
    owner: str
    attempt_number: int
    lease_expires_at: datetime


class CheckpointProjection(Contract):
    id: str
    step_id: str
    effect_key: str


class RunEventProjection(Contract):
    id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
