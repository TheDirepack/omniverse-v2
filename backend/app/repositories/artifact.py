from typing import Any
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload

from app.db.schema import Artifact, ArtifactRelation

class ArtifactRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_universe(self, universe_id: int, limit: int = 100, offset: int = 0) -> list[Artifact]:
        stmt = select(Artifact).where(Artifact.universe_id == universe_id).offset(offset).limit(limit)
        return list(self.session.exec(stmt).all())

    def search_artifacts(self, universe_id: int, query: str, limit: int = 100, offset: int = 0) -> list[Artifact]:
        stmt = select(Artifact).where(
            Artifact.universe_id == universe_id,
            (Artifact.name.contains(query)) | (Artifact.description.contains(query))
        ).offset(offset).limit(limit)
        return list(self.session.exec(stmt).all())

    def get_artifact_with_details(self, artifact_id: int) -> Artifact | None:
        stmt = (
            select(Artifact)
            .where(Artifact.id == artifact_id)
            .options(
                joinedload(Artifact.relations_from),
                joinedload(Artifact.relations_to)
            )
        )
        return self.session.exec(stmt).first()
