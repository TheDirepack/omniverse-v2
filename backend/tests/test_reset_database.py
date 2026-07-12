from sqlmodel import Session, select

from app.db.schema import (
    Artifact,
    ArtifactRelation,
    Universe,
)
from app.db.session import engine
