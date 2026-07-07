from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, delete, select

from app.db.extrapolation_schema import Theory


class TheoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_theory(self, theory: Theory) -> Theory:
        self.session.add(theory)
        return theory

    def delete_theory_for_universe(self, universe_id: int):
        self.session.exec(delete(Theory).where(Theory.universe_id == universe_id))

    def get_all_theories(
        self, limit: int = 100, offset: int = 0, fields: list[str] | None = None
    ) -> Sequence[Any]:
        stmt = select(Theory).order_by(Theory.created_at.desc())
        if fields:
            proj_fields = [getattr(Theory, f) for f in fields if hasattr(Theory, f)]
            if proj_fields:
                stmt = select(*proj_fields).order_by(Theory.created_at.desc())
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def get_theories_by_universe_ids(
        self,
        universe_ids: list[int],
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(Theory).where(Theory.universe_id.in_(universe_ids))
        if fields:
            proj_fields = [getattr(Theory, f) for f in fields if hasattr(Theory, f)]
            if proj_fields:
                stmt = select(*proj_fields).where(Theory.universe_id.in_(universe_ids))
        return self.session.exec(stmt.offset(offset).limit(limit)).all()
