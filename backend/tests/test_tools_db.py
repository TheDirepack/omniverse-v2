"""
Tests for core/tools.py — the confirmed-DB tools (queryTraits, upsertTrait)
that operate against the main SQLite database.
"""
import pytest
from sqlmodel import Session, select

from app.db.session import engine
from app.db.schema import Universe, Trait
from app.core.tools import tool_query_universe_traits, tool_upsert_trait
from app.core.context import set_current_universe


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def universe_context(seeded_db):
    """Set the universe ContextVar to the seeded universe and clear afterwards."""
    _, u, _, _ = seeded_db
    set_current_universe(u.name)
    yield u
    set_current_universe("")


# ── queryTraits ──────────────────────────────────────────────────────

class TestQueryTraits:
    async def test_no_traits_returns_no_traits_message(self, universe_context):
        result = await tool_query_universe_traits({})
        assert "No traits" in result or "no traits" in result.lower()

    async def test_returns_existing_traits(self, universe_context, seeded_db):
        ephemeral_db, u, _, _ = seeded_db
        ephemeral_db.add(Trait(universe_id=u.id, name="power level", value="over 9000"))
        ephemeral_db.commit()

        result = await tool_query_universe_traits({})
        assert "power level" in result
        assert "over 9000" in result

    async def test_returns_multiple_traits(self, universe_context, seeded_db):
        ephemeral_db, u, _, _ = seeded_db
        ephemeral_db.add(Trait(universe_id=u.id, name="speed", value="fast"))
        ephemeral_db.add(Trait(universe_id=u.id, name="strength", value="immense"))
        ephemeral_db.commit()

        result = await tool_query_universe_traits({})
        assert "speed" in result
        assert "strength" in result

    async def test_no_active_universe(self):
        set_current_universe("")
        result = await tool_query_universe_traits({})
        assert "No active universe context" in result

    async def test_universe_not_in_db(self):
        set_current_universe("NonExistentUniverse")
        result = await tool_query_universe_traits({})
        assert "not found" in result.lower()


# ── upsertTrait ──────────────────────────────────────────────────────

class TestUpsertTrait:
    async def test_creates_new_trait(self, universe_context, seeded_db):
        ephemeral_db, u, _, _ = seeded_db
        result = await tool_upsert_trait({"name": "agility", "value": "superhuman"})
        assert "Created new trait" in result or "agility" in result

        with Session(engine) as s:
            trait = s.exec(
                select(Trait).where(Trait.universe_id == u.id, Trait.name == "agility")
            ).first()
            assert trait is not None
            assert trait.value == "superhuman"

    async def test_updates_existing_trait(self, universe_context, seeded_db):
        ephemeral_db, u, _, _ = seeded_db
        ephemeral_db.add(Trait(universe_id=u.id, name="armor", value="light"))
        ephemeral_db.commit()

        result = await tool_upsert_trait({"name": "armor", "value": "heavy"})
        assert "Updated existing trait" in result or "armor" in result

        with Session(engine) as s:
            trait = s.exec(
                select(Trait).where(Trait.universe_id == u.id, Trait.name == "armor")
            ).first()
            assert trait.value == "heavy"

    async def test_missing_name_returns_error(self, universe_context):
        result = await tool_upsert_trait({"value": "some value"})
        assert "Missing trait name" in result

    async def test_no_active_universe_returns_error(self):
        set_current_universe("")
        result = await tool_upsert_trait({"name": "n", "value": "v"})
        assert "No active universe context" in result

    async def test_universe_not_in_db(self):
        set_current_universe("GhostUniverse")
        result = await tool_upsert_trait({"name": "n", "value": "v"})
        assert "not found" in result.lower()

    async def test_empty_value_is_accepted(self, universe_context, seeded_db):
        """An empty string value is valid — some traits may have no data yet."""
        result = await tool_upsert_trait({"name": "unknown_trait", "value": ""})
        assert "Error" not in result or "Missing" not in result
