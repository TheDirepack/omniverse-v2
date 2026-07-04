import pytest
from unittest.mock import patch
from sqlmodel import Session, select
from app.core.tools import (
    tool_query_universe_traits,
    tool_upsert_trait,
    tool_query_unconfirmed_traits,
    tool_save_unconfirmed_trait,
    tool_delete_unconfirmed_trait
)
from app.db.schema import Universe, Trait
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait
from app.db.session import engine
from app.db.unconfirmed_session import engine as unconfirmed_engine, init_unconfirmed_db
from app.core.context import set_current_universe

@pytest.fixture
def universe_setup():
    with Session(engine) as session:
        u = Universe(name="Test Universe")
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u

@pytest.fixture(autouse=True)
def setup_unconfirmed_db():
    init_unconfirmed_db()
    yield

@pytest.fixture
def unconfirmed_universe_setup():
    with Session(unconfirmed_engine) as session:
        u = UnconfirmedUniverse(name="Unconfirmed Universe")
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u

@pytest.mark.asyncio
async def test_tool_query_universe_traits(universe_setup):
    set_current_universe(universe_setup.name)
    with Session(engine) as session:
        t = Trait(universe_id=universe_setup.id, name="Test Trait", value="Test Value")
        session.add(t)
        session.commit()

    result = await tool_query_universe_traits({})
    assert "Test Trait: Test Value" in result

@pytest.mark.asyncio
async def test_tool_upsert_trait(universe_setup):
    set_current_universe(universe_setup.name)
    
    # Create
    result = await tool_upsert_trait({"name": "New Trait", "value": "New Value"})
    assert "Created" in result and "New Trait" in result
    
    # Update
    result = await tool_upsert_trait({"name": "New Trait", "value": "Updated Value"})
    assert "Updated" in result and "New Trait" in result
    
    with Session(engine) as session:
        t = session.exec(select(Trait).where(Trait.name == "New Trait")).one()
        assert t.value == "Updated Value"

@pytest.mark.asyncio
async def test_tool_query_unconfirmed_traits(unconfirmed_universe_setup):
    set_current_universe(unconfirmed_universe_setup.name)
    with Session(unconfirmed_engine) as session:
        t = UnconfirmedTrait(
            universe_id=unconfirmed_universe_setup.id, 
            name="Unconfirmed Trait", 
            value="Unconfirmed Value",
            category="Cosmology"
        )
        session.add(t)
        session.commit()

    result = await tool_query_unconfirmed_traits({})
    assert "Unconfirmed Trait: Unconfirmed Value" in result
    assert "category: Cosmology" in result

@pytest.mark.asyncio
async def test_tool_save_unconfirmed_trait(unconfirmed_universe_setup):
    set_current_universe(unconfirmed_universe_setup.name)
    
    result = await tool_save_unconfirmed_trait({
        "name": "New Unconfirmed",
        "value": "New Value",
        "category": "Magic"
    })
    assert "Saved" in result and "New Unconfirmed" in result
    
    with Session(unconfirmed_engine) as session:
        t = session.exec(select(UnconfirmedTrait).where(UnconfirmedTrait.name == "New Unconfirmed")).one()
        assert t.category == "Magic"
        assert t.value == "New Value"

@pytest.mark.asyncio
async def test_tool_delete_unconfirmed_trait(unconfirmed_universe_setup):
    set_current_universe(unconfirmed_universe_setup.name)
    
    with Session(unconfirmed_engine) as session:
        t = UnconfirmedTrait(
            universe_id=unconfirmed_universe_setup.id, 
            name="To Delete", 
            value="Bye"
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        t_id = t.id

    result = await tool_delete_unconfirmed_trait({"trait_id": t_id})
    assert "Deleted" in result and str(t_id) in result
    
    with Session(unconfirmed_engine) as session:
        t = session.get(UnconfirmedTrait, t_id)
        assert t is None


def test_build_freshness_comparison_report_prefers_fresh_over_none():
    from app.core.tools import build_freshness_comparison_report

    report = build_freshness_comparison_report({
        "http://fresh.example": "[SOURCE FRESHNESS SIGNALS]\nStaleness warning: none detected\n[END SIGNALS]\nBody text here",
        "http://unavailable.example": None,
    })

    assert "CANDIDATE: http://fresh.example" in report
    assert "Staleness warning: none detected" in report
    assert "Body text here" not in report  # only the signal block, not the full page, is included
    assert "CANDIDATE: http://unavailable.example" in report
    assert "Unavailable" in report
