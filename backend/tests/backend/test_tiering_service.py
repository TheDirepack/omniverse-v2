from app.db.schema import TierSystem, Universe
from app.services.tiering_service import TieringService


class TestTieringService:
    def test_get_active_rubric_none(self, clean_db):
        svc = TieringService(clean_db)
        assert svc.get_active_rubric() is None
        svc.close()

    def test_create_and_get_latest_rubric(self, clean_db):
        svc = TieringService(clean_db)
        created = svc.create_rubric("definition1", version=1)
        assert created.id is not None
        latest = svc.get_latest_rubric()
        assert latest is not None
        assert latest.version == 1
        svc.close()

    def test_amend_rubric(self, clean_db):
        svc = TieringService(clean_db)
        old = svc.create_rubric("old def", version=1)
        new = svc.amend_rubric(old.id, "new def", "test reason")
        assert new.id != old.id
        assert new.system_definition == "new def"
        assert new.amendment_reason == "test reason"
        assert new.parent_id == old.id
        # Old rubric should be inactive
        old_rubric = clean_db.get(TierSystem, old.id)
        assert old_rubric.is_active is False
        svc.close()

    def test_slot_world(self, clean_db):
        svc = TieringService(clean_db)
        rubric = svc.create_rubric("rubric", version=1)
        u = Universe(name="SlotWorld")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        wt = svc.slot_world(u.id, rubric.id, 3, "feat")
        assert wt.id is not None
        assert wt.tier_number == 3
        svc.close()

    def test_clear_world_tier(self, clean_db):
        svc = TieringService(clean_db)
        rubric = svc.create_rubric("r", version=1)
        u = Universe(name="ClearUni")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        svc.slot_world(u.id, rubric.id, 5, "j")
        svc.clear_world_tier(u.id)
        assert svc.get_world_tier(u.id) is None
        svc.close()

    def test_create_and_get_anomaly(self, clean_db):
        svc = TieringService(clean_db)
        u = Universe(name="AnomSvc")
        clean_db.add(u)
        clean_db.commit()
        clean_db.refresh(u)
        a = svc.create_anomaly(u.id, "weird behavior")
        assert a.id is not None
        all_a = svc.get_all_anomalies()
        assert any(an.id == a.id for an in all_a)
        svc.close()

    def test_get_world_tiers(self, clean_db):
        svc = TieringService(clean_db)
        assert svc.get_world_tiers([999]) == []
        svc.close()

    def test_close_noop(self):
        svc = TieringService()
        svc.close()

    def test_injected_session(self, clean_db):
        svc = TieringService(clean_db)
        assert svc.get_active_rubric() is None
        svc.close()

    def test_amend_rubric_nonexistent(self, clean_db):
        svc = TieringService(clean_db)
        new = svc.amend_rubric(99999, "new", "reason")
        assert new is not None
        assert new.parent_id is None
        svc.close()
