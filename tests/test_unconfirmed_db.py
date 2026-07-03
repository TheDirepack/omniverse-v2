"""
Tests for the unconfirmed staging database layer:
  - UnconfirmedUniverse / UnconfirmedTrait schema
  - unconfirmed_session engine + init_unconfirmed_db()
  - Tool functions that read/write the unconfirmed DB
"""
import os
import pytest
from sqlmodel import SQLModel, Session, create_engine, select

# ── Test-only unconfirmed DB setup ─────────────────────────────────
# conftest.py already points UNCONFIRMED_DB_URL at the temp path
from app.db.unconfirmed_session import engine as unconfirmed_engine, init_unconfirmed_db
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait, unconfirmed_metadata


@pytest.fixture(autouse=True)
def clean_unconfirmed_db():
    """Drop and recreate unconfirmed tables before each test."""
    unconfirmed_metadata.drop_all(unconfirmed_engine)
    init_unconfirmed_db()
    yield
    unconfirmed_metadata.drop_all(unconfirmed_engine)


@pytest.fixture
def uc_session():
    with Session(unconfirmed_engine) as session:
        yield session


# ── Schema tests ────────────────────────────────────────────────────

class TestUnconfirmedUniverse:
    def test_create(self, uc_session):
        u = UnconfirmedUniverse(name="TestUniverse")
        uc_session.add(u)
        uc_session.commit()
        uc_session.refresh(u)
        assert u.id is not None
        assert u.name == "TestUniverse"
        assert u.is_explored is False

    def test_unique_name(self, uc_session):
        uc_session.add(UnconfirmedUniverse(name="Dup"))
        uc_session.commit()
        with pytest.raises(Exception):
            uc_session.add(UnconfirmedUniverse(name="Dup"))
            uc_session.commit()

    def test_optional_fields_default_null(self, uc_session):
        u = UnconfirmedUniverse(name="Minimal")
        uc_session.add(u)
        uc_session.commit()
        uc_session.refresh(u)
        assert u.source_wikis is None
        assert u.raw_data is None
        assert u.summary is None
        assert u.research_status is None

    def test_created_at_set_automatically(self, uc_session):
        u = UnconfirmedUniverse(name="Timestamped")
        uc_session.add(u)
        uc_session.commit()
        uc_session.refresh(u)
        assert u.created_at is not None


class TestUnconfirmedTrait:
    def _make_universe(self, session, name: str = "Marvel") -> UnconfirmedUniverse:
        u = UnconfirmedUniverse(name=name)
        session.add(u)
        session.flush()
        return u

    def test_create_trait(self, uc_session):
        u = self._make_universe(uc_session)
        t = UnconfirmedTrait(universe_id=u.id, name="speed", value="faster than light")
        uc_session.add(t)
        uc_session.commit()
        uc_session.refresh(t)
        assert t.id is not None
        assert t.name == "speed"
        assert t.value == "faster than light"

    def test_optional_metadata_fields(self, uc_session):
        u = self._make_universe(uc_session)
        t = UnconfirmedTrait(
            universe_id=u.id, name="trait", value="val",
            category="Magic System", canon_status="Verified",
            reference="https://example.com", wiki_source="Wikiname",
            confidence="high",
        )
        uc_session.add(t)
        uc_session.commit()
        uc_session.refresh(t)
        assert t.category == "Magic System"
        assert t.canon_status == "Verified"
        assert t.confidence == "high"

    def test_nonexistent_universe_fk_raises(self, uc_session):
        t = UnconfirmedTrait(universe_id=9999, name="n", value="v")
        with pytest.raises(Exception):
            uc_session.add(t)
            uc_session.commit()

    def test_created_at_set_automatically(self, uc_session):
        u = self._make_universe(uc_session)
        t = UnconfirmedTrait(universe_id=u.id, name="n", value="v")
        uc_session.add(t)
        uc_session.commit()
        uc_session.refresh(t)
        assert t.created_at is not None


# ── Tool function tests ─────────────────────────────────────────────

class TestUnconfirmedToolFunctions:
    """Tests for the five unconfirmed-DB tools in core/tools.py."""

    @pytest.fixture(autouse=True)
    def set_universe(self):
        from app.core.context import set_current_universe
        set_current_universe("DC")
        yield
        set_current_universe("")

    async def test_save_and_query_unconfirmed_trait(self):
        from app.core.tools import tool_save_unconfirmed_trait, tool_query_unconfirmed_traits

        result = await tool_save_unconfirmed_trait({
            "name": "super strength",
            "value": "100 tons",
            "category": "Hard Tech",
            "canon_status": "Verified",
            "confidence": "high",
        })
        assert "Saved unconfirmed trait" in result
        assert "super strength" in result

        query_result = await tool_query_unconfirmed_traits({})
        assert "super strength" in query_result
        assert "100 tons" in query_result

    async def test_save_creates_universe_if_missing(self):
        from app.core.tools import tool_save_unconfirmed_trait
        # "DC" universe doesn't exist yet — save should auto-create it
        result = await tool_save_unconfirmed_trait({"name": "flight", "value": "yes"})
        assert "Saved" in result

        # Universe now exists in unconfirmed DB
        with Session(unconfirmed_engine) as s:
            u = s.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == "DC")).first()
            assert u is not None

    async def test_query_returns_error_when_no_universe(self):
        from app.core.tools import tool_query_unconfirmed_traits
        # Universe "DC" has no rows yet — should return no-data message
        result = await tool_query_unconfirmed_traits({})
        assert "No unconfirmed data" in result or "No unconfirmed traits" in result

    async def test_delete_unconfirmed_trait(self):
        from app.core.tools import tool_save_unconfirmed_trait, tool_delete_unconfirmed_trait

        await tool_save_unconfirmed_trait({"name": "speed", "value": "mach 10"})
        with Session(unconfirmed_engine) as s:
            u = s.exec(select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == "DC")).first()
            trait = s.exec(select(UnconfirmedTrait).where(UnconfirmedTrait.universe_id == u.id)).first()
            tid = trait.id

        result = await tool_delete_unconfirmed_trait({"trait_id": tid})
        assert "Deleted" in result

    async def test_delete_nonexistent_trait(self):
        from app.core.tools import tool_delete_unconfirmed_trait
        result = await tool_delete_unconfirmed_trait({"trait_id": 99999})
        assert "not found" in result.lower()

    async def test_delete_missing_trait_id(self):
        from app.core.tools import tool_delete_unconfirmed_trait
        result = await tool_delete_unconfirmed_trait({})
        assert "Missing trait_id" in result

    async def test_save_missing_name(self):
        from app.core.tools import tool_save_unconfirmed_trait
        result = await tool_save_unconfirmed_trait({"value": "val"})
        assert "Missing trait name" in result

    async def test_operations_without_context_error(self):
        from app.core.context import set_current_universe
        from app.core.tools import tool_save_unconfirmed_trait, tool_query_unconfirmed_traits

        set_current_universe("")
        save_result = await tool_save_unconfirmed_trait({"name": "n", "value": "v"})
        query_result = await tool_query_unconfirmed_traits({})
        assert "No active universe context" in save_result
        assert "No active universe context" in query_result
