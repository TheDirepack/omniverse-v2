import pytest
from sqlmodel import Session

from app.db.extrapolation_schema import ExtrapolationModel, Theory
from app.repositories.theory import TheoryRepository
from tests.conftest import extrapolation_engine


@pytest.fixture
def theory_session():
    ExtrapolationModel.metadata.create_all(extrapolation_engine)
    with Session(extrapolation_engine) as session:
        yield session
    with Session(extrapolation_engine) as session:
        session.exec(Theory.__table__.delete())
        session.commit()


class TestTheoryRepository:
    def test_create_theory(self, theory_session):
        repo = TheoryRepository(theory_session)
        t = Theory(universe_id=1, theory_text="test")
        result = repo.create_theory(t)
        theory_session.commit()
        assert result.id is not None
        assert result.universe_id == 1

    def test_get_all_theories(self, theory_session):
        repo = TheoryRepository(theory_session)
        repo.create_theory(Theory(universe_id=1, theory_text="a"))
        repo.create_theory(Theory(universe_id=2, theory_text="b"))
        theory_session.commit()
        results = repo.get_all_theories(limit=10)
        assert len(results) >= 2

    def test_get_all_theories_with_fields(self, theory_session):
        repo = TheoryRepository(theory_session)
        repo.create_theory(Theory(universe_id=1, theory_text="c"))
        theory_session.commit()
        results = repo.get_all_theories(fields=["universe_id"])
        assert len(results) >= 1

    def test_get_all_theories_with_invalid_field(self, theory_session):
        repo = TheoryRepository(theory_session)
        repo.create_theory(Theory(universe_id=1, theory_text="d"))
        theory_session.commit()
        results = repo.get_all_theories(fields=["nonexistent"])
        assert len(results) >= 1

    def test_delete_theory_for_universe(self, theory_session):
        repo = TheoryRepository(theory_session)
        repo.create_theory(Theory(universe_id=10, theory_text="x"))
        theory_session.commit()
        repo.delete_theory_for_universe(10)
        theory_session.commit()
        remaining = repo.get_all_theories()
        assert all(t.universe_id != 10 for t in remaining)

    def test_get_theories_by_universe_ids(self, theory_session):
        repo = TheoryRepository(theory_session)
        repo.create_theory(Theory(universe_id=1, theory_text="a"))
        repo.create_theory(Theory(universe_id=2, theory_text="b"))
        repo.create_theory(Theory(universe_id=3, theory_text="c"))
        theory_session.commit()
        results = repo.get_theories_by_universe_ids([1, 3])
        assert len(results) == 2

    def test_get_theories_by_universe_ids_with_fields(self, theory_session):
        repo = TheoryRepository(theory_session)
        repo.create_theory(Theory(universe_id=5, theory_text="e"))
        theory_session.commit()
        results = repo.get_theories_by_universe_ids([5], fields=["universe_id"])
        assert len(results) == 1
