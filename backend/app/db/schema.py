from sqlmodel import SQLModel, Field, Column, ForeignKey
from sqlalchemy import UniqueConstraint
from typing import Optional, List
from datetime import datetime

class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Optional[str] = None

class ProviderConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[str] = None

class ProviderKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider_id: int = Field(sa_column=Column(ForeignKey("providerconfig.id", ondelete="CASCADE")))
    api_key: str
    priority: int = Field(default=0)

class AgentRouteFallback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_type: str
    priority: int = Field(default=0)
    provider_id: Optional[int] = Field(default=None, sa_column=Column(ForeignKey("providerconfig.id", ondelete="SET NULL")))
    models: Optional[str] = None


class Universe(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    summary: Optional[str] = None
    raw_data: Optional[str] = None
    is_explored: bool = Field(default=False)

class Trait(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id", "name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    name: str
    value: str

class TierSystem(SQLModel, table=True):
    # A tier rubric. Rubrics are persistent: once is_active is set, new worlds
    # should be slotted into the existing rubric rather than triggering a full
    # redesign. version increments only when the rubric itself is amended
    # (e.g. a new tier boundary is added to resolve a genuine anomaly).
    # parent_id links an amended rubric back to the version it replaced, so
    # the rubric's evolution can be audited.
    id: Optional[int] = Field(default=None, primary_key=True)
    system_definition: str
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="tiersystem.id")
    amendment_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WorldTier(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    system_id: int = Field(foreign_key="tiersystem.id")
    tier_number: int
    justification: str

class Anomaly(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="universe.id")
    description: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)

class ExecutionState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str
    node_name: str
    thought: str
    status: str
    state_snapshot: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ModelConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_name: str
    provider_id: int = Field(foreign_key="providerconfig.id")

class Entity(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("universe_id", "name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    entity_type: str
    universe_id: int = Field(foreign_key="universe.id")
    canonical: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EntityAlias(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("alias", "universe_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_id: int = Field(foreign_key="entity.id")
    alias: str = Field(index=True)
    universe_id: int = Field(foreign_key="universe.id")

class Predicate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    category: Optional[str] = None
    parent_predicate_id: Optional[int] = Field(default=None, foreign_key="predicate.id")

class PredicateAlias(SQLModel, table=True):
    alias: str = Field(primary_key=True)
    predicate_id: Optional[int] = Field(default=None, foreign_key="predicate.id")

class Claim(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="entity.id")
    predicate_id: Optional[int] = Field(default=None, foreign_key="predicate.id")
    predicate: str = Field(index=True) # Stores canonical predicate (deprecated)
    object_entity_id: Optional[int] = Field(default=None, foreign_key="entity.id")
    object_literal: Optional[str] = None
    source_reference: Optional[str] = None
    source_wiki: Optional[str] = None
    support_count: int = Field(default=1)
    contradiction_count: int = Field(default=0)
    status: str = Field(default="PENDING")  # PENDING, VERIFIED, CONTRADICTED, SUPERSEDED
    universe_scope: Optional[int] = Field(default=None, foreign_key="universe.id")
    superseded_by: Optional[int] = Field(default=None, foreign_key="claim.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ClaimAttribute(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    claim_id: int = Field(foreign_key="claim.id", ondelete="CASCADE")
    key: str = Field(index=True)
    value: str

class InferenceRule(SQLModel, table=True):
    # A composition rule: predicate_1 followed by predicate_2 (via a shared
    # intermediate entity) implies implied_predicate directly between the
    # outer subject/object. Proposed by an LLM pair (proposer + independent
    # critic), never auto-approved: human_approved must be set explicitly
    # before the rule is used in path materialization, since a bad rule
    # silently corrupts every inference derived from it.
    id: Optional[int] = Field(default=None, primary_key=True)
    predicate_1: str
    predicate_2: str
    implied_predicate: str
    rule_type: str = Field(default="compose")  # "compose" | "block"
    status: str = Field(default="PROPOSED")  # PROPOSED, CRITIQUED, APPROVED, REJECTED
    proposer_model: Optional[str] = None
    proposer_rationale: Optional[str] = None
    critic_model: Optional[str] = None
    critic_verdict: Optional[str] = None  # APPROVE, REJECT, REVISE
    critic_rationale: Optional[str] = None
    human_approved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InferredClaim(SQLModel, table=True):
    # A materialized path-composition, not directly asserted by any source.
    # contradicts_claim_id is a flag for semantic review only — it must never
    # be auto-resolved, since a mismatch may mean the rule composed correctly
    # but the asserted claim is a legitimate exception, not an error.
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="entity.id")
    predicate: str
    object_id: int = Field(foreign_key="entity.id")
    derived_from_rule_id: int = Field(foreign_key="inferencerule.id")
    path_claim_ids: str  # JSON list of Claim.id forming this path
    contradicts_claim_id: Optional[int] = Field(default=None, foreign_key="claim.id")
    reviewed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CandidateHealth(SQLModel, table=True):
    candidate_hash: str = Field(primary_key=True)
    provider_id: int = Field(index=True)
    key_id: Optional[int] = Field(default=None, index=True)
    model: str = Field(index=True)
    failure_count: int = Field(default=0)
    disabled_until: Optional[datetime] = None
