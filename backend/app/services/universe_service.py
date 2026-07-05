from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import Universe, Trait
from app.repositories.universe import UniverseRepository

class UniverseService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session

    def _get_repo(self) -> UniverseRepository:
        if self.session:
            return UniverseRepository(self.session)
        # For simplicity in this fix, we'll use a new session. 
        # In a real app, this should be handled by a dependency.
        return UniverseRepository(Session(engine))

    def get_universe(self, name: str) -> Optional[Universe]:
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_by_name(name)

    def get_universe_by_id(self, universe_id: int) -> Optional[Universe]:
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_by_id(universe_id)

    def get_all_universes(self) -> Sequence[Universe]:
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_all()

    def create_universe(self, name: str) -> Universe:
        with Session(engine) if not self.session else self.session as session:
            universe = Universe(name=name, summary=None, is_explored=False)
            repo = UniverseRepository(session)
            return repo.create(universe)

    def mark_explored(self, universe_id: int):
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = True
                repo.update(universe)

    def reset_explored(self, universe_id: int) -> bool:
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = False
                repo.update(universe)
                return True
            return False

    def reset_all_explored(self) -> int:
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universes = repo.get_all()
            count = 0
            for u in universes:
                if u.is_explored:
                    u.is_explored = False
                    repo.update(u)
                    count += 1
            return count

    def get_traits(self, universe_ids: Optional[str] = None) -> List[Dict[str, Any]]:
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            if universe_ids:
                ids = [int(id_str) for id_str in universe_ids.split(",") if id_str.strip()]
                traits = repo.get_traits_by_universe_ids(ids)
            else:
                all_universes = repo.get_all()
                traits = []
                for u in all_universes:
                    traits.extend(repo.get_traits(u.id))
            return [t.model_dump() for t in traits]

    def delete_universe(self, universe_id: int):
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                repo.delete_traits(universe_id)
                from app.repositories.tiering import TieringRepository
                from app.repositories.theory import TheoryRepository
                from app.db.extrapolation_session import engine as extra_engine
                
                with Session(engine) as tier_session:
                    tier_repo = TieringRepository(tier_session)
                    tier_repo.delete_world_tier(universe_id)
                    tier_repo.delete_anomalies(universe_id)
                
                with Session(extra_engine) as theory_session:
                    theory_repo = TheoryRepository(theory_session)
                    theory_repo.delete_theory_for_universe(universe_id)
                
                repo.delete(universe)

    def update_summary(self, universe_id: int, summary: str):
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.summary = summary
                repo.update(universe)

