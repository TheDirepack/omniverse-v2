from typing import List, Optional, Sequence
from sqlmodel import Session, select, delete
from app.db.schema import TierSystem, WorldTier, Anomaly

class TieringRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_active_rubric(self) -> Optional[TierSystem]:
        return self.session.exec(
            select(TierSystem).where(TierSystem.is_active == True).order_by(TierSystem.version.desc())
        ).first()

    def create_rubric(self, tier_system: TierSystem) -> TierSystem:
        self.session.add(tier_system)
        self.session.commit()
        self.session.refresh(tier_system)
        return tier_system

    def update_rubric(self, tier_system: TierSystem) -> TierSystem:
        self.session.add(tier_system)
        self.session.commit()
        self.session.refresh(tier_system)
        return tier_system

    def get_latest_rubric(self) -> Optional[TierSystem]:
        return self.session.exec(select(TierSystem).order_by(TierSystem.created_at.desc())).first()

    def get_world_tier(self, universe_id: int) -> Optional[WorldTier]:
        return self.session.exec(select(WorldTier).where(WorldTier.universe_id == universe_id)).first()

    def get_world_tiers_by_universe_ids(self, universe_ids: List[int]) -> Sequence[WorldTier]:
        return self.session.exec(select(WorldTier).where(WorldTier.universe_id.in_(universe_ids))).all()

    def upsert_world_tier(self, world_tier: WorldTier) -> WorldTier:
        # Delete existing for this universe first
        self.delete_world_tier(world_tier.universe_id)
        self.session.add(world_tier)
        self.session.commit()
        self.session.refresh(world_tier)
        return world_tier

    def delete_world_tier(self, universe_id: int):
        self.session.exec(delete(WorldTier).where(WorldTier.universe_id == universe_id))
        self.session.commit()

    def create_anomaly(self, anomaly: Anomaly) -> Anomaly:
        self.session.add(anomaly)
        self.session.commit()
        self.session.refresh(anomaly)
        return anomaly

    def get_all_anomalies(self) -> Sequence[Anomaly]:
        return self.session.exec(select(Anomaly).order_by(Anomaly.detected_at.desc())).all()

    def delete_anomalies(self, universe_id: int):
        self.session.exec(delete(Anomaly).where(Anomaly.universe_id == universe_id))
        self.session.commit()
