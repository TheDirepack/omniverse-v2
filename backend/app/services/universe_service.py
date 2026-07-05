from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import Universe, Trait
from app.repositories.universe import UniverseRepository

class UniverseService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or Session(engine)
        self.repo = UniverseRepository(self.session)

    def get_universe(self, name: str) -> Optional[Universe]:
        return self.repo.get_by_name(name)

    def get_universe_by_id(self, universe_id: int) -> Optional[Universe]:
        return self.repo.get_by_id(universe_id)

    def get_all_universes(self) -> Sequence[Universe]:
        return self.repo.get_all()

    def create_universe(self, name: str) -> Universe:
        universe = Universe(name=name, summary=None, is_explored=False)
        return self.repo.create(universe)

    def mark_explored(self, universe_id: int):
        universe = self.repo.get_by_id(universe_id)
        if universe:
            universe.is_explored = True
            self.repo.update(universe)

    def reset_explored(self, universe_id: int):
        universe = self.repo.get_by_id(universe_id)
        if universe:
            universe.is_explored = False
            self.repo.update(universe)

    def reset_all_explored(self) -> int:
        universes = self.repo.get_all()
        count = 0
        for u in universes:
            if u.is_explored:
                u.is_explored = False
                self.repo.update(u)
                count += 1
        return count

    def get_traits(self, universe_ids: Optional[str] = None) -> List[Dict[str, Any]]:
        if universe_ids:
            ids = [int(id_str) for id_str in universe_ids.split(",") if id_str.strip()]
            traits = self.repo.get_traits_by_universe_ids(ids)
        else:
            # This is a bit inefficient, but for now we'll just fetch all if no IDs
            # In a real app we might want pagination.
            all_universes = self.repo.get_all()
            traits = []
            for u in all_universes:
                traits.extend(self.repo.get_traits(u.id))
        
        return [t.model_dump() for t in traits]

    def delete_universe(self, universe_id: int):
        universe = self.repo.get_by_id(universe_id)
        if universe:
            # Delete related data first
            from app.services.tiering_service import TieringService
            from app.services.theory_service import TheoryService
            
            # We need to be careful about circular imports, but services are separate
            # In this case, we can just use the repos directly or call services.
            # Let's use repos to avoid circularity if possible, or just import inside.
            
            # I'll implement the cleanup in a coordinator or just here with imports.
            self.repo.delete_traits(universe_id)
            
            # Use other repos for cleanup
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
            
            self.repo.delete(universe)

    def update_summary(self, universe_id: int, summary: str):
        universe = self.repo.get_by_id(universe_id)
        if universe:
            universe.summary = summary
            self.repo.update(universe)
