from collections.abc import Sequence
from typing import Any

from sqlmodel import Session

from app.db.extrapolation_schema import Theory
from app.db.extrapolation_session import engine as extra_engine
from app.repositories.theory import TheoryRepository


class TheoryService:
    def __init__(self, session: Session | None = None):
        self.session = session
        self._repo = None

    @property
    def repo(self) -> TheoryRepository:
        if self._repo is None:
            self._repo = TheoryRepository(self.session or Session(extra_engine))
        return self._repo

    def upsert_theory(
        self, universe_id: int, theory_text: str, auditor_feedback: str
    ) -> Theory:
        self.repo.delete_theory_for_universe(universe_id)
        theory = Theory(
            universe_id=universe_id,
            theory_text=theory_text,
            auditor_feedback=auditor_feedback,
        )
        res = self.repo.create_theory(theory)
        self.repo.session.commit()
        return res

    def get_all_theories(
        self, limit: int = 100, offset: int = 0, fields: list[str] | None = None
    ) -> Sequence[Any]:
        return self.repo.get_all_theories(limit=limit, offset=offset, fields=fields)

    def get_theories_by_universe_ids(
        self,
        universe_ids: list[int],
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        return self.repo.get_theories_by_universe_ids(
            universe_ids, limit=limit, offset=offset, fields=fields
        )

    def delete_theory(self, universe_id: int):
        self.repo.delete_theory_for_universe(universe_id)
        self.repo.session.commit()

    def close(self):
        """Closes the internal session if it was lazily created."""
        if self._repo and not self.session:
            self._repo.session.close()
            self._repo = None
