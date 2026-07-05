from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import TierSystem, WorldTier, Anomaly
from app.repositories.tiering import TieringRepository

class TieringService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or Session(engine)
        self.repo = TieringRepository(self.session)

    def get_active_rubric(self) -> Optional[TierSystem]:
        return self.repo.get_active_rubric()

    def get_latest_rubric(self) -> Optional[TierSystem]:
        return self.repo.get_latest_rubric()

    def create_rubric(self, definition: str, version: int = 1) -> TierSystem:
        rubric = TierSystem(system_definition=definition, version=version, is_active=True)
        return self.repo.create_rubric(rubric)

    def amend_rubric(self, old_rubric_id: int, new_definition: str, reason: str) -> TierSystem:
        old_rubric = self.session.get(TierSystem, old_rubric_id)
        if old_rubric:
            old_rubric.is_active = False
            self.repo.update_rubric(old_rubric)
        
        new_version = (self.session.get(TierSystem, old_rubric_id).version or 1) + 1 if old_rubric else 1
        new_rubric = TierSystem(
            system_definition=new_definition,
            version=new_version,
            is_active=True,
            parent_id=old_rubric_id if old_rubric else None,
            amendment_reason=reason[:2000]
        )
        return self.repo.create_rubric(new_rubric)

    def slot_world(self, universe_id: int, rubric_id: int, tier: int, justification: str) -> WorldTier:
        wt = WorldTier(universe_id=universe_id, system_id=rubric_id, tier_number=tier, justification=justification)
        return self.repo.upsert_world_tier(wt)

    def clear_world_tier(self, universe_id: int):
        self.repo.delete_world_tier(universe_id)

    def create_anomaly(self, universe_id: int, description: str) -> Anomaly:
        anomaly = Anomaly(universe_id=universe_id, description=description)
        return self.repo.create_anomaly(anomaly)

    def get_all_anomalies(self) -> Sequence[Anomaly]:
        return self.repo.get_all_anomalies()

    def get_world_tier(self, universe_id: int) -> Optional[WorldTier]:
        return self.repo.get_world_tier(universe_id)

    def get_world_tiers(self, universe_ids: List[int]) -> Sequence[WorldTier]:
        return self.repo.get_world_tiers_by_universe_ids(universe_ids)
