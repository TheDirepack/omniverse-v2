import hashlib
from datetime import datetime

from sqlalchemy import Column, ForeignKey, MetaData, UniqueConstraint
from sqlmodel import Field, LargeBinary, SQLModel

unconfirmed_metadata = MetaData()


class UnconfirmedModel(SQLModel):
    metadata = unconfirmed_metadata


class UnconfirmedUniverse(UnconfirmedModel, table=True):
    __tablename__ = "unconfirmed_universe"

    id: int | None = Field(default=None, primary_key=True)
    universe_uuid: str | None = Field(default=None, index=True)
    name: str = Field(index=True, unique=True)
    source_wikis: str | None = None
    raw_data: str | None = None
    summary: str | None = None
    research_status: str | None = None
    is_explored: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UnconfirmedClaim(UnconfirmedModel, table=True):
    __tablename__ = "unconfirmed_claim"

    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(foreign_key="unconfirmed_universe.id")
    subject: str
    context: str | None = None
    predicate: str
    object_val: str
    reference: str | None = None
    wiki_source: str | None = None
    confidence: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AcquisitionArtifact(UnconfirmedModel, table=True):
    __tablename__ = "acquisition_artifact"

    id: int | None = Field(default=None, primary_key=True)
    content_hash: str = Field(index=True)
    source_url: str = Field(index=True)
    content_type: str
    raw_bytes: bytes | None = Field(sa_column=Column(LargeBinary, nullable=True))
    extracted_text: str | None = None
    structured_data: str | None = None
    engine_name: str | None = None
    engine_version: str | None = None
    fetch_duration_ms: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @staticmethod
    def compute_hash(content: str | bytes) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()


class WorldAcquisitionUsage(UnconfirmedModel, table=True):
    __tablename__ = "world_acquisition_usage"
    __table_args__ = (
        UniqueConstraint("artifact_id", "universe_uuid", "run_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    artifact_id: int = Field(
        sa_column=Column(ForeignKey("acquisition_artifact.id", ondelete="CASCADE"))
    )
    universe_uuid: str = Field(index=True)
    run_id: str = Field(index=True)
    usage_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProvenanceEdge(UnconfirmedModel, table=True):
    __tablename__ = "provenance_edge"

    id: int | None = Field(default=None, primary_key=True)
    source_artifact_id: int = Field(
        sa_column=Column(ForeignKey("acquisition_artifact.id", ondelete="CASCADE"))
    )
    target_type: str
    target_id: int
    relation: str
    run_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
