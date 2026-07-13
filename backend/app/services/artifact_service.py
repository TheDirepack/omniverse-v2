from typing import Any, Sequence
from sqlmodel import Session, select
from app.db.schema import Artifact
from app.db.session import engine
from app.repositories.artifact import ArtifactRepository


class ArtifactService:
    def __init__(self, session: Session | None = None):
        self.session = session
        self._repo: ArtifactRepository | None = None

    @property
    def repo(self) -> ArtifactRepository:
        if self._repo is None:
            self._repo = ArtifactRepository(self.session or Session(engine))
        return self._repo

    def list_artifacts(
        self, universe_id: int, search_query: str | None = None, limit: int = 100, offset: int = 0
    ) -> Sequence[Artifact]:
        if search_query:
            return self.repo.search_artifacts(universe_id, search_query, limit, offset)
        return self.repo.get_by_universe(universe_id, limit, offset)

    def get_artifact_details(self, artifact_id: int) -> Artifact | None:
        return self.repo.get_artifact_with_details(artifact_id)
