from app.db.schema import Anomaly, TierSystem, Universe, WorldTier
from app.repositories.tiering import TieringRepository


class TestTieringRepository:
    def test_get_active_rubric_none(self, clean_db):
        repo = TieringRepository(clean_db)
        assert repo.get_active_rubric() is None

    def test_get_active_rubric(self, clean_db):
        repo = TieringRepository(clean_db)
        ts = TierSystem(system_definition="test", is_active=True, version=1)
        repo.create_rubric(ts)
        clean_db.commit()
        assert repo.get_active_rubric() is not None

    def test_get_latest_rubric(self, clean_db):
        repo = TieringRepository(clean_db)
        ts = TierSystem(system_definition="v1", version=1)
        repo.create_rubric(ts)
        clean_db.commit()
        result = repo.get_latest_rubric()
        assert result is not None
        assert result.version == 1

    def test_get_world_tier_none(self, clean_db):
        repo = TieringRepository(clean_db)
        assert repo.get_world_tier(999) is None

    def test_upsert_world_tier(self, clean_db):
        repo = TieringRepository(clean_db)
        u = Universe(name="TierUni")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        ts = TierSystem(system_definition="rubric", is_active=True, version=1)
        repo.create_rubric(ts)
        clean_db.commit()
        clean_db.refresh(ts)
        wt = WorldTier(
            universe_id=u.id, system_id=ts.id, tier_number=5, justification="ok"
        )
        result = repo.upsert_world_tier(wt)
        clean_db.commit()
        assert result.id is not None

    def test_get_world_tiers_by_universe_ids(self, clean_db):
        repo = TieringRepository(clean_db)
        u = Universe(name="MultiTier")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        ts = TierSystem(system_definition="r", is_active=True, version=1)
        repo.create_rubric(ts)
        clean_db.commit()
        clean_db.refresh(ts)
        repo.upsert_world_tier(
            WorldTier(
                universe_id=u.id, system_id=ts.id, tier_number=3, justification="j"
            )
        )
        clean_db.commit()
        results = repo.get_world_tiers_by_universe_ids([u.id, 999])
        assert len(results) >= 1

    def test_delete_world_tier(self, clean_db):
        repo = TieringRepository(clean_db)
        u = Universe(name="DelTier")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        ts = TierSystem(system_definition="r", is_active=True, version=1)
        repo.create_rubric(ts)
        clean_db.commit()
        clean_db.refresh(ts)
        repo.upsert_world_tier(
            WorldTier(
                universe_id=u.id, system_id=ts.id, tier_number=1, justification="j"
            )
        )
        clean_db.commit()
        repo.delete_world_tier(u.id)
        clean_db.commit()
        assert repo.get_world_tier(u.id) is None

    def test_create_anomaly(self, clean_db):
        repo = TieringRepository(clean_db)
        u = Universe(name="AnomUni")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        a = Anomaly(universe_id=u.id, description="weird")
        result = repo.create_anomaly(a)
        clean_db.commit()
        assert result.id is not None

    def test_get_all_anomalies(self, clean_db):
        repo = TieringRepository(clean_db)
        u = Universe(name="AnomUni2")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        repo.create_anomaly(Anomaly(universe_id=u.id, description="a1"))
        clean_db.commit()
        all_a = repo.get_all_anomalies()
        assert len(all_a) >= 1

    def test_delete_anomalies(self, clean_db):
        repo = TieringRepository(clean_db)
        u = Universe(name="AnomDel")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        repo.create_anomaly(Anomaly(universe_id=u.id, description="delme"))
        clean_db.commit()
        repo.delete_anomalies(u.id)
        clean_db.commit()
        after = repo.get_all_anomalies()
        assert all(a.universe_id != u.id for a in after)
