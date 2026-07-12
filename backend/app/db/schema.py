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
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    type: str = Field(index=True)
    name: str | None = Field(default=None, index=True)
    confidence: str | None = None
    freshness: str | None = None
    verification_status: str = Field(default="PENDING")
    evidence_refs: str = Field(default="[]", index=True)
    support_count: int = Field(default=0, index=True)
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
    section: str | None = Field(default=None, index=True)
    source_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    __table_args__ = (UniqueConstraint("universe_id", "source_url", "section"),)


class EvidenceChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    evidence_id: int = Field(foreign_key="evidence.id", ondelete="CASCADE")
    content: str
    chunk_index: int
    created_at: datetime = Field(default_factory=datetime.utcnow)



class ArtifactVersion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    artifact_id: int = Field(
        sa_column=Column(ForeignKey("artifact.id", ondelete="CASCADE"), nullable=False),
    )
    version: int = Field(index=True)
    payload_json: str
    evidence_refs: str
    created_at: datetime = Field(default_factory=datetime.utcnow)






class CandidateHealth(SQLModel, table=True):
    candidate_hash: str = Field(primary_key=True)
    provider_id: int = Field(index=True)
    key_id: int | None = Field(default=None, index=True)
    model: str = Field(index=True)
    failure_count: int = Field(default=0)
    last_failure_at: datetime | None = Field(default=None)
    disabled_until: datetime | None = Field(default=None)


