import pytest
from app.db.extrapolation_schema import ExtrapolationModel, Theory
from app.services.theory_service import TheoryService
from app.repositories.theory import TheoryRepository
from sqlmodel import Session
from tests.conftest import extrapolation_engine


@pytest.fixture(autouse=True)
def clean_extra():
    ExtrapolationModel.metadata.create_all(extrapolation_engine)
    yield
    with Session(extrapolation_engine) as s:
        s.exec(Theory.__table__.delete())
        s.commit()


class TestTheoryService:
    def test_upsert_theory(self):
        svc = TheoryService()
        result = svc.upsert_theory(1, "test theory", "feedback")
        assert result.id is not None
        assert result.theory_text == "test theory"
        assert result.auditor_feedback == "feedback"
        svc.close()

    def test_upsert_replaces_existing(self):
        svc = TheoryService()
        svc.upsert_theory(1, "first", "fb1")
        svc.close()
        svc2 = TheoryService()
        svc2.upsert_theory(1, "second", "fb2")
        all_t = svc2.get_all_theories()
        assert len(all_t) == 1
        assert all_t[0].theory_text == "second"
        svc2.close()

    def test_get_all_theories(self):
        svc = TheoryService()
        svc.upsert_theory(1, "a", "f1")
        svc.upsert_theory(2, "b", "f2")
        results = svc.get_all_theories(limit=10)
        assert len(results) >= 2
        svc.close()

    def test_get_all_theories_with_fields(self):
        svc = TheoryService()
        svc.upsert_theory(1, "c", "f3")
        results = svc.get_all_theories(fields=["universe_id"])
        assert len(results) >= 1
        svc.close()

    def test_get_theories_by_universe_ids(self):
        svc = TheoryService()
        svc.upsert_theory(1, "x", "fx")
        svc.upsert_theory(2, "y", "fy")
        results = svc.get_theories_by_universe_ids([1])
        assert len(results) == 1
        svc.close()

    def test_delete_theory(self):
        svc = TheoryService()
        svc.upsert_theory(10, "del me", "fb")
        svc.delete_theory(10)
        remaining = svc.get_all_theories()
        assert all(t.universe_id != 10 for t in remaining)
        svc.close()

    def test_close_noop_when_no_repo(self):
        svc = TheoryService()
        svc.close()

    def test_injected_session(self):
        with Session(extrapolation_engine) as session:
            svc = TheoryService(session=session)
            result = svc.upsert_theory(99, "injected session", "ok")
            assert result.id is not None
            svc.close()

    def test_get_all_theories_with_limit_offset(self):
        svc = TheoryService()
        for i in range(5):
            svc.upsert_theory(i, f"theory_{i}", "fb")
        results = svc.get_all_theories(limit=2, offset=0)
        assert len(results) == 2
        svc.close()
