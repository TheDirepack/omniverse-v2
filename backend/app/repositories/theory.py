from typing import List, Sequence
from sqlmodel import Session, select, delete
from app.db.extrapolation_schema import Theory

class TheoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_theory(self, theory: Theory) -> Theory:
        self.session.add(theory)
        self.session.commit()
        self.session.refresh(theory)
        return theory

    def delete_theory_for_universe(self, universe_id: int):
        self.session.exec(delete(Theory).where(Theory.universe_id == universe_id))
        self.session.commit()

    def get_all_theories(self) -> Sequence[Theory]:
        return self.session.exec(select(Theory).order_by(Theory.created_at.desc())).all()

    def get_theories_by_universe_ids(self, universe_ids: List[int]) -> Sequence[Theory]:
        return self.session.exec(select(Theory).where(Theory.universe_id.in_(universe_ids))).all()
