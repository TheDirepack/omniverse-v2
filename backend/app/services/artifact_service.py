from collections.abc import Sequence

from sqlmodel import Session

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
        self, universe_id: int | None = None, search_query: str | None = None, limit: int = 100, offset: int = 0
    ) -> Sequence[Artifact]:
        if search_query and universe_id is not None:
            return self.repo.search_artifacts(universe_id, search_query, limit, offset)
        if search_query:
            return self.repo.search_all_artifacts(search_query, limit, offset)
        if universe_id is not None:
            return self.repo.get_by_universe(universe_id, limit, offset)
        return self.repo.get_all(limit, offset)

    def get_artifact_details(self, artifact_id: int) -> Artifact | None:
        return self.repo.get_artifact_with_details(artifact_id)



    def get_artifact_by_type_and_name(self, content_type: str, name: str) -> Artifact | None:
        """Get artifact by type and name."""
        if not self._repo:
            self._repo = ArtifactRepository(self.session)
        return self._repo.get_by_type_and_name(content_type, name)

    async def create_artifact(
        self,
        content_type: str,
        title: str,
        description: str | None = None,
        details: str | None = None,
        raw_content: str | None = None,
        universe_id: int | None = None,
    ) -> Artifact:
        """Create a new artifact."""
        from app.db.schema import Artifact

        # Get universe if not provided
        if universe_id is None and self.session:
            from app.core.context import get_current_universe
            current_universe = get_current_universe()
            if current_universe:
                universe_id = current_universe.id

        if universe_id is None:
            raise ValueError("universe_id must be provided")

        artifact = Artifact(
            type=content_type,
            name=title,
            description=description,
            details=details,
            raw=raw_content,
            universe_id=universe_id,
        )

        if self.session:
            self.session.add(artifact)
            await self.session.commit()
            await self.session.refresh(artifact)

        return artifact
