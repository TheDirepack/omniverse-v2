from datetime import datetime
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Column, Field, ForeignKey, SQLModel


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str | None = None


class ProviderConfig(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    provider_type: str | None = None
    base_url: str | None = None
    models: str | None = None


class ProviderKey(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    provider_id: int = Field(
        sa_column=Column(
            ForeignKey("providerconfig.id", ondelete="CASCADE"), nullable=False
        )
    )
    api_key: str
    priority: int = Field(default=0)


class AgentRouteFallback(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_type: str
    priority: int = Field(default=0)
    provider_id: int | None = Field(
        default=None,
        sa_column=Column(ForeignKey("providerconfig.id", ondelete="SET NULL")),
    )
    models: str | None = None


class Universe(SQLModel, table=True):
    __table_args__ = ()
    id: int | None = Field(default=None, primary_key=True)
    uuid: str = Field(
        default_factory=lambda: str(uuid4()), index=True, unique=True
    )
    slug: str | None = Field(default=None, index=True, unique=True)
    name: str = Field(index=True)
    franchise: str | None = None
    category: str | None = None
    continuity: str | None = None
    era: str | None = None
    parent_id: int | None = Field(default=None, foreign_key="universe.id")
    summary: str | None = None
    raw_data: str | None = None
    is_explored: bool = Field(default=False)

    @property
    def display_name(self) -> str:
        if (
            (self.era and self.name == self.era)
            or (self.continuity and self.name == self.continuity)
        ):
            return self.franchise or self.name
        return self.name


class UniverseRelation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("from_universe_id", "to_universe_id", "relation_type"),
    )
    id: int | None = Field(default=None, primary_key=True)
    from_universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    to_universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    relation_type: str = Field(index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TierSystem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    system_definition: str
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    parent_id: int | None = Field(default=None, foreign_key="tiersystem.id")
    amendment_reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorldTier(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id"),)
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    system_id: int = Field(foreign_key="tiersystem.id")
    tier_number: int
    justification: str


class Anomaly(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    description: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionState(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str
    node_name: str
    thought: str
    status: str
    state_snapshot: str
    duration_ms: float | None = Field(default=None)
    token_usage: int | None = Field(default=None)
    cost: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModelConfig(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_name: str
    provider_id: int = Field(foreign_key="providerconfig.id")


class Artifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    type: str = Field(index=True)
    name: str | None = Field(default=None, index=True)
    confidence: str | None = None
    freshness: str | None = None
    verification_status: str = Field(default="PENDING")
    evidence_id: int | None = Field(default=None, foreign_key="evidence.id")
    source_reference: str | None = None
    source_wiki: str | None = None
    payload_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ArtifactRelation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    from_artifact_id: int = Field(
        sa_column=Column(ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False)
    )
    to_artifact_id: int = Field(
        sa_column=Column(ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False)
    )
    relation_type: str = Field(index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)



class Evidence(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    source_url: str = Field(index=True)
    source_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    evidence_id: int = Field(foreign_key="evidence.id", ondelete="CASCADE")
    content: str
    chunk_index: int
    created_at: datetime = Field(default_factory=datetime.utcnow)




class InferenceRule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    predicate_1: str
    predicate_2: str
    implied_predicate: str
    rule_type: str = Field(default="compose")
    status: str = Field(default="PROPOSED")
    proposer_model: str | None = None
    proposer_rationale: str | None = None
    critic_model: str | None = None
    critic_verdict: str | None = None
    critic_rationale: str | None = None
    human_approved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InferredClaim(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="artifact.id")
    predicate: str
    object_id: int = Field(foreign_key="artifact.id")
    derived_from_rule_id: int = Field(
        sa_column=Column(
            ForeignKey("inferencerule.id", ondelete="CASCADE"), nullable=False
        )
    )
    contradicts_claim_id: int | None = Field(default=None, foreign_key="artifact.id")
    reviewed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InferredClaimPath(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    inferred_claim_id: int = Field(foreign_key="inferredclaim.id", ondelete="CASCADE")
    claim_id: int = Field(foreign_key="artifact.id", ondelete="CASCADE")
    hop_index: int


class CandidateHealth(SQLModel, table=True):
    candidate_hash: str = Field(primary_key=True)
    provider_id: int = Field(index=True)
    key_id: int | None = Field(default=None, index=True)
    model: str = Field(index=True)
    failure_count: int = Field(default=0)
    last_failure_at: datetime | None = Field(default=None)
    disabled_until: datetime | None = Field(default=None)


class Entity(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id", "name"),)
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    name: str = Field(index=True)
    entity_type: str = Field(default="Unknown")


class EntityAlias(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id", "alias"),)
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    alias: str = Field(index=True)
    entity_id: int = Field(foreign_key="entity.id")


class Predicate(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("canonical_name"),)
    id: int | None = Field(default=None, primary_key=True)
    canonical_name: str = Field(index=True)


class Claim(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("subject_id", "context", "predicate_id", "object_entity_id", "object_literal"),)
    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="entity.id")
    context: str = Field(default="")
    predicate_id: int = Field(foreign_key="predicate.id")
    predicate: str = Field(default="")
    object_entity_id: int | None = Field(default=None, foreign_key="entity.id")
    object_literal: str | None = Field(default=None)
    source_reference: str | None = Field(default=None)
    source_wiki: str | None = Field(default=None)
    evidence_chunk_id: int | None = Field(default=None, foreign_key="evidencechunk.id")
    support_count: int = Field(default=0)
    universe_scope: int = Field(foreign_key="universe.id")
    status: str = Field(default="VERIFIED")
    source_unconfirmed_id: int | None = Field(default=None)


class ClaimAttribute(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("claim_id", "key"),)
    id: int | None = Field(default=None, primary_key=True)
    claim_id: int = Field(foreign_key="claim.id")
    key: str = Field(index=True)
    value: str = Field(default="")


class UnconfirmedClaim(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("subject", "context", "predicate", "object_val"),)
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    subject: str = Field(index=True)
    context: str = Field(default="")
    predicate: str = Field(index=True)
    object_val: str = Field(index=True)
    reference: str | None = Field(default=None)
    wiki_source: str | None = Field(default=None)
    confidence: str = Field(default="")
