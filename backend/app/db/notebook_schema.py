import hashlib
from datetime import datetime

from sqlalchemy import Column, ForeignKey, MetaData, UniqueConstraint
from sqlmodel import Field, LargeBinary, SQLModel

notebook_metadata = MetaData()


class NotebookModel(SQLModel):
    metadata = notebook_metadata


class TimelineEntry(NotebookModel, table=True):
    __tablename__ = "timeline_entry"
    id: int | None = Field(default=None, primary_key=True)
    universe_uuid: str = Field(index=True)
    title: str
    date: str | None = None
    era: str | None = None
    summary: str | None = None
    description: str | None = None
    importance: int = Field(default=1)
    confidence: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TimelineParticipant(NotebookModel, table=True):
    __tablename__ = "timeline_participant"
    id: int | None = Field(default=None, primary_key=True)
    timeline_id: int = Field(foreign_key="timeline_entry.id", ondelete="CASCADE")
    entity_id: int
    role: str | None = None

class TimelineLocation(NotebookModel, table=True):
    __tablename__ = "timeline_location"
    id: int | None = Field(default=None, primary_key=True)
    timeline_id: int = Field(foreign_key="timeline_entry.id", ondelete="CASCADE")
    location_id: int

class TimelineSource(NotebookModel, table=True):
    __tablename__ = "timeline_source"
    id: int | None = Field(default=None, primary_key=True)
    timeline_id: int = Field(foreign_key="timeline_entry.id", ondelete="CASCADE")
    source_id: int

class TimelineClaim(NotebookModel, table=True):
    __tablename__ = "timeline_claim"
    id: int | None = Field(default=None, primary_key=True)
    timeline_id: int = Field(foreign_key="timeline_entry.id", ondelete="CASCADE")
    claim_id: int


class NotebookUniverse(NotebookModel, table=True):

    __tablename__ = "notebook_universe"

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





class AcquisitionArtifact(NotebookModel, table=True):
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


class WorldAcquisitionUsage(NotebookModel, table=True):
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


class ProvenanceEdge(NotebookModel, table=True):
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


class ResearchSource(NotebookModel, table=True):
    __tablename__ = "research_source"

    id: int | None = Field(default=None, primary_key=True)
    universe_uuid: str = Field(index=True)
    url: str = Field(index=True)
    title: str | None = None
    reason_saved: str | None = None
    coverage: str | None = None
    reliability: str | None = None
    extraction_status: str = Field(default="UNREAD")
    created_at: datetime = Field(default_factory=datetime.utcnow)




class NotebookEntry(NotebookModel, table=True):
    __tablename__ = "notebook_entry"

    id: int | None = Field(default=None, primary_key=True)
    universe_uuid: str = Field(index=True)
    title: str
    summary: str
    details: str | None = None
    kind: str = Field(index=True)
    status: str = Field(default="OPEN")
    priority: int = Field(default=0)
    run_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)




class Snapshot(NotebookModel, table=True):
    __tablename__ = "snapshot"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    snapshot_type: str = Field(default="FULL")  # FULL, UNVERIFIED
    data_blob: bytes | None = Field(sa_column=Column(LargeBinary, nullable=True))
    snapshot_metadata: str | None = None
