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
        sa_column=Column(ForeignKey("providerconfig.id", ondelete="CASCADE"))
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
        if (self.era and self.name == self.era) or (self.continuity and self.name == self.continuity):
            return self.franchise or self.name
        return self.name


class UniverseRelation(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("from_universe_id", "to_universe_id", "relation_type"),
    )
    id: int | None = Field(default=None, primary_key=True)
    from_universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
    to_universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
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
    universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
    system_id: int = Field(foreign_key="tiersystem.id")
    tier_number: int
    justification: str


class Anomaly(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
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


class Entity(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id", "name"),)
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    entity_type: str
    universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
    canonical_entity_id: int | None = Field(default=None, foreign_key="entity.id")
    canonical: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EntityAlias(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("alias", "universe_id"),)
    id: int | None = Field(default=None, primary_key=True)
    entity_id: int = Field(foreign_key="entity.id")
    alias: str = Field(index=True)
    universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))


class Predicate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    canonical_name: str = Field(index=True, unique=True)
    description: str | None = None
    category: str | None = None
    parent_predicate_id: int | None = Field(default=None, foreign_key="predicate.id")


class PredicateAlias(SQLModel, table=True):
    alias: str = Field(primary_key=True)
    predicate_id: int | None = Field(default=None, foreign_key="predicate.id")


class Evidence(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
    source_url: str = Field(index=True)
    source_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    evidence_id: int = Field(foreign_key="evidence.id", ondelete="CASCADE")
    content: str
    chunk_index: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Claim(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("subject_id", "predicate_id", "object_entity_id"),
        UniqueConstraint("subject_id", "predicate_id", "object_literal"),
    )
    id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="entity.id")
    context: str | None = Field(default=None, index=True)
    predicate_id: int | None = Field(default=None, foreign_key="predicate.id")
    predicate: str = Field(index=True)
    object_entity_id: int | None = Field(default=None, foreign_key="entity.id")
    object_literal: str | None = None
    evidence_chunk_id: int | None = Field(default=None, foreign_key="evidencechunk.id")
    artifact_id: int | None = Field(default=None)
    source_reference: str | None = None
    source_wiki: str | None = None
    support_count: int = Field(default=1)
    contradiction_count: int = Field(default=0)
    status: str = Field(default="PENDING")
    universe_scope: int | None = Field(default=None, sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE")))
    source_unconfirmed_id: int | None = Field(default=None, index=True)
    superseded_by: int | None = Field(default=None, foreign_key="claim.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClaimAttribute(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    claim_id: int = Field(foreign_key="claim.id", ondelete="CASCADE")
    key: str = Field(index=True)
    value: str


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
    subject_id: int = Field(foreign_key="entity.id")
    predicate: str
    object_id: int = Field(foreign_key="entity.id")
    derived_from_rule_id: int = Field(
        sa_column=Column(ForeignKey("inferencerule.id", ondelete="CASCADE"))
    )
    contradicts_claim_id: int | None = Field(default=None, foreign_key="claim.id")
    reviewed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InferredClaimPath(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    inferred_claim_id: int = Field(foreign_key="inferredclaim.id", ondelete="CASCADE")
    claim_id: int = Field(foreign_key="claim.id", ondelete="CASCADE")
    hop_index: int


class CandidateHealth(SQLModel, table=True):
    candidate_hash: str = Field(primary_key=True)
    provider_id: int = Field(index=True)
    key_id: int | None = Field(default=None, index=True)
    model: str = Field(index=True)
    failure_count: int = Field(default=0)
    last_failure_at: datetime | None = Field(default=None)
    disabled_until: datetime | None = Field(default=None)
