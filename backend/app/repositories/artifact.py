from sqlalchemy.orm import joinedload
from sqlmodel import Session, select

from app.db.schema import Artifact


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

    def get_all(self, limit: int = 100, offset: int = 0) -> list[Artifact]:
        stmt = select(Artifact).offset(offset).limit(limit)
        return list(self.session.exec(stmt).all())

    def search_all_artifacts(self, query: str, limit: int = 100, offset: int = 0) -> list[Artifact]:
        stmt = select(Artifact).where(
            (Artifact.name.contains(query)) | (Artifact.description.contains(query))
        ).offset(offset).limit(limit)
        return list(self.session.exec(stmt).all())


# Additional method for API
    def get_by_type_and_name(self, content_type: str, name: str) -> Artifact | None:
        """Get artifact by type and name."""
        if not self.session:
            return None

        from app.db.schema import Artifact

        query = select(Artifact).where(
            (Artifact.content_type == content_type) &
            (Artifact.name == name)
        )
        return self.session.exec(query).first()
