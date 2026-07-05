from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.extrapolation_session import engine as extra_engine
from app.db.extrapolation_schema import Theory
from app.repositories.theory import TheoryRepository

class TheoryService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or Session(extra_engine)
        self.repo = TheoryRepository(self.session)

    def upsert_theory(self, universe_id: int, theory_text: str, auditor_feedback: str) -> Theory:
        self.repo.delete_theory_for_universe(universe_id)
        theory = Theory(
            universe_id=universe_id,
            theory_text=theory_text,
            auditor_feedback=auditor_feedback
        )
        return self.repo.create_theory(theory)

    def get_all_theories(self) -> Sequence[Theory]:
        return self.repo.get_all_theories()

    def get_theories_by_universe_ids(self, universe_ids: List[int]) -> Sequence[Theory]:
        return self.repo.get_theories_by_universe_ids(universe_ids)

    def delete_theory(self, universe_id: int):
        self.repo.delete_theory_for_universe(universe_id)
