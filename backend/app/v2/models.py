from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, _dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, _dialect: object
    ) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class World(Base):
    __tablename__ = "world"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    franchise: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    continuity: Mapped[str | None] = mapped_column(String)
    era: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("world.id"))
    aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)


class Continuity(Base):
    __tablename__ = "continuity"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class TimelineBranch(Base):
    __tablename__ = "timeline_branch"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    parent_branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("timeline_branch.id")
    )
    divergence_point: Mapped[str | None] = mapped_column(String)


class Subject(Base):
    __tablename__ = "subject"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class SubjectRelation(Base):
    __tablename__ = "subject_relation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_subject_id: Mapped[str] = mapped_column(
        ForeignKey("subject.id"), nullable=False
    )
    target_subject_id: Mapped[str] = mapped_column(
        ForeignKey("subject.id"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String, nullable=False)


class PolicyDefinition(Base):
    __tablename__ = "policy_definition"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    policy_type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Source(Base):
    __tablename__ = "source"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    canonical_url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    source_class: Mapped[str] = mapped_column(
        String, nullable=False, default="SECONDARY"
    )
    publisher: Mapped[str | None] = mapped_column(String)
    lineage_id: Mapped[str | None] = mapped_column(String)


class SourceRevision(Base):
    __tablename__ = "source_revision"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    blob_hash: Mapped[str | None] = mapped_column(String(64))
    retrieved_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String)
    fetch_error_code: Mapped[str | None] = mapped_column(String)
    extractor_name: Mapped[str | None] = mapped_column(String)
    extractor_version: Mapped[str | None] = mapped_column(String)
    extraction_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("source_id", "content_hash"),)


class EvidenceFragment(Base):
    __tablename__ = "evidence_fragment"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_revision_id: Mapped[str] = mapped_column(
        ForeignKey("source_revision.id"), nullable=False
    )
    locator: Mapped[str] = mapped_column(String, nullable=False)
    exact_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    normalized_statement: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String)
    subject_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    continuity: Mapped[str | None] = mapped_column(String)
    temporal_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    support_role: Mapped[str | None] = mapped_column(String)
    extraction_confidence: Mapped[int | None] = mapped_column(Integer)
    world_id: Mapped[str | None] = mapped_column(ForeignKey("world.id"))
    era_or_timepoint: Mapped[str | None] = mapped_column(String)
    branch_id: Mapped[str | None] = mapped_column(String)
    conditions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    __table_args__ = (
        Index(
            "ix_evidence_freshness_scope",
            "world_id",
            "continuity",
            "era_or_timepoint",
            "branch_id",
        ),
    )


class Citation(Base):
    __tablename__ = "citation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    evidence_fragment_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_fragment.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, nullable=False)


class ResearchWorkspace(Base):
    __tablename__ = "research_workspace"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("run_target.id"), nullable=False)
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    continuity: Mapped[str] = mapped_column(String, nullable=False)
    era_or_timepoint: Mapped[str] = mapped_column(
        String, nullable=False, default="unspecified"
    )
    branch_id: Mapped[str] = mapped_column(String, nullable=False, default="main")
    conditions_key: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    brief_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint("run_id", "target_id"),)
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}


class SearchLead(Base):
    __tablename__ = "search_lead"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("research_workspace.id"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    source_class: Mapped[str] = mapped_column(
        String, nullable=False, default="SECONDARY"
    )
    publisher: Mapped[str | None] = mapped_column(String)
    lineage_id: Mapped[str | None] = mapped_column(String)
    __table_args__ = (UniqueConstraint("workspace_id", "canonical_url"),)


class CoverageRecord(Base):
    __tablename__ = "coverage_record"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("research_workspace.id"), nullable=False
    )
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    continuity: Mapped[str] = mapped_column(String, nullable=False)
    era_or_timepoint: Mapped[str] = mapped_column(
        String, nullable=False, default="unspecified"
    )
    branch_id: Mapped[str] = mapped_column(String, nullable=False, default="main")
    conditions_key: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String, nullable=False)
    indicators_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "world_id",
            "domain",
            "continuity",
            "era_or_timepoint",
            "branch_id",
            "conditions_key",
        ),
        Index(
            "ix_coverage_freshness_scope",
            "world_id",
            "continuity",
            "era_or_timepoint",
            "branch_id",
            "conditions_key",
            "status",
        ),
    )


class WorkflowSummary(Base):
    __tablename__ = "workflow_summary"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("run_target.id"), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("run_id", "target_id"),)


class IntegrationEffect(Base):
    __tablename__ = "integration_effect"
    effect_key: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(String, nullable=False)
    node_revision_id: Mapped[str] = mapped_column(
        ForeignKey("canon_node_revision.id"), nullable=False
    )


class ModelStepEffect(Base):
    __tablename__ = "model_step_effect"
    effect_key: Mapped[str] = mapped_column(String, primary_key=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("run_step.id"), nullable=False)
    task: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    manifest_id: Mapped[str | None] = mapped_column(ForeignKey("context_manifest.id"))
    model_call_id: Mapped[str | None] = mapped_column(String)


class StepEffect(Base):
    __tablename__ = "step_effect"
    step_id: Mapped[str] = mapped_column(ForeignKey("run_step.id"), primary_key=True)
    effect_type: Mapped[str] = mapped_column(String, nullable=False)
    effect_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class ResearchGapRecord(Base):
    __tablename__ = "research_gap"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("research_workspace.id"), nullable=False
    )
    gap_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class MaterialProposalRecord(Base):
    __tablename__ = "material_proposal"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("research_workspace.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class MaterialProposalFieldRecord(Base):
    __tablename__ = "material_proposal_field"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("material_proposal.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint("proposal_id", "name"),)


class ProposalFieldEvidence(Base):
    __tablename__ = "proposal_field_evidence"
    proposal_field_id: Mapped[str] = mapped_column(
        ForeignKey("material_proposal_field.id"), primary_key=True
    )
    evidence_fragment_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_fragment.id"), primary_key=True
    )
    support_role: Mapped[str] = mapped_column(String, primary_key=True)


class ClaimConflict(Base):
    __tablename__ = "claim_conflict"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_field_id: Mapped[str] = mapped_column(
        ForeignKey("material_proposal_field.id"), nullable=False
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("research_workspace.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    resolution_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AuditDecisionRecord(Base):
    __tablename__ = "audit_decision"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("material_proposal.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    assertion_type: Mapped[str] = mapped_column(String, nullable=False)
    assertion_id: Mapped[str] = mapped_column(String, nullable=False)
    evidence_fragment_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String, nullable=False)
    model_call_id: Mapped[str | None] = mapped_column(String)
    manifest_id: Mapped[str | None] = mapped_column(ForeignKey("context_manifest.id"))
    __table_args__ = (
        UniqueConstraint("proposal_id", "assertion_type", "assertion_id"),
    )


class PromotionDecision(Base):
    __tablename__ = "promotion_decision"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("material_proposal.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String, nullable=False)
    policy_version: Mapped[str] = mapped_column(
        String, nullable=False, default="promotion.v1"
    )
    audit_manifest_id: Mapped[str | None] = mapped_column(
        ForeignKey("context_manifest.id")
    )


class Run(Base):
    __tablename__ = "run"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    outcome: Mapped[str | None] = mapped_column(String)
    cancel_requested_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}


class RunTarget(Base):
    __tablename__ = "run_target"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("run_id", "world_id"),)


class RunStep(Base):
    __tablename__ = "run_step"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    target_id: Mapped[str] = mapped_column(ForeignKey("run_target.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column()
    retry_due_at: Mapped[datetime | None] = mapped_column()
    output_refs_json: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("target_id", "position"),)


class StepAttempt(Base):
    __tablename__ = "step_attempt"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("run_step.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column()
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("step_id", "attempt_number"),)


class Checkpoint(Base):
    __tablename__ = "checkpoint"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("run_step.id"), nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    effect_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    output_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("run.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    effect_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)


class ToolEvent(Base):
    __tablename__ = "tool_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("run_step.id"))
    status: Mapped[str] = mapped_column(String, nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    blob_hash: Mapped[str | None] = mapped_column(String(64))
    source_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_revision.id")
    )
    extract_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_class: Mapped[str | None] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)


class ContextManifest(Base):
    __tablename__ = "context_manifest"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("run.id"))
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)


class ModelCall(Base):
    __tablename__ = "model_call"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("run_step.id"), nullable=False)
    task: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    selected_evidence_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String)
    model_id: Mapped[str | None] = mapped_column(String)
    response_id: Mapped[str | None] = mapped_column(String)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    manifest_id: Mapped[str] = mapped_column(
        ForeignKey("context_manifest.id"), nullable=False
    )


class Provider(Base):
    __tablename__ = "provider"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version_id}


class ProviderModel(Base):
    __tablename__ = "provider_model"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("provider.id"), nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    output_limit: Mapped[int | None] = mapped_column(Integer)
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_structured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    supports_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("provider_id", "model_name"),)


class CredentialRef(Base):
    __tablename__ = "credential_ref"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("provider.id"), nullable=False)
    opaque_ref: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Route(Base):
    __tablename__ = "provider_route"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint("task", "position"),)


class RouteCandidate(Base):
    __tablename__ = "provider_route_candidate"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    route_id: Mapped[str] = mapped_column(
        ForeignKey("provider_route.id"), nullable=False
    )
    model_id: Mapped[str] = mapped_column(
        ForeignKey("provider_model.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint("route_id", "position"),)


class CandidateHealth(Base):
    __tablename__ = "provider_candidate_health"
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("provider_route_candidate.id"), primary_key=True
    )
    cooldown_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_class: Mapped[str | None] = mapped_column(String)


class CredentialHealth(Base):
    __tablename__ = "provider_credential_health"
    credential_id: Mapped[str] = mapped_column(
        ForeignKey("credential_ref.id"), primary_key=True
    )
    cooldown_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_class: Mapped[str | None] = mapped_column(String)


class StructuredSummaryRevision(Base):
    __tablename__ = "structured_summary_revision"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    manifest_id: Mapped[str] = mapped_column(
        ForeignKey("context_manifest.id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("manifest_id", "revision_number"),)


class AcquisitionCache(Base):
    __tablename__ = "acquisition_cache"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_url: Mapped[str] = mapped_column(String, nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision_id: Mapped[str] = mapped_column(
        ForeignKey("source_revision.id"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class CanonNode(Base):
    __tablename__ = "canon_node"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("world.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    modality: Mapped[str | None] = mapped_column(String)


class CanonNodeRevision(Base):
    __tablename__ = "canon_node_revision"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("canon_node.id"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("node_id", "revision_number"),)


class RelationshipAssertion(Base):
    __tablename__ = "relationship_assertion"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("canon_node.id"), nullable=False
    )
    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("canon_node.id"), nullable=False
    )


class RelationshipRevision(Base):
    __tablename__ = "relationship_revision"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    assertion_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_assertion.id"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    relation_type: Mapped[str] = mapped_column(String, nullable=False)
    scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(String)
    valid_to: Mapped[str | None] = mapped_column(String)
    __table_args__ = (UniqueConstraint("assertion_id", "revision_number"),)


class NodeEvidence(Base):
    __tablename__ = "node_evidence"
    node_revision_id: Mapped[str] = mapped_column(
        ForeignKey("canon_node_revision.id"), primary_key=True
    )
    evidence_fragment_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_fragment.id"), primary_key=True
    )
    field_name: Mapped[str] = mapped_column(String, primary_key=True)


class RelationshipEvidence(Base):
    __tablename__ = "relationship_evidence"
    relationship_revision_id: Mapped[str] = mapped_column(
        ForeignKey("relationship_revision.id"), primary_key=True
    )
    evidence_fragment_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_fragment.id"), primary_key=True
    )
    field_name: Mapped[str] = mapped_column(
        String, primary_key=True, default="relationship"
    )


class SeedRun(Base):
    __tablename__ = "seed_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    importer_version: Mapped[str] = mapped_column(String, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
