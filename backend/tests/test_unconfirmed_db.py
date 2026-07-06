import pytest
import os
from sqlmodel import Session, create_engine, select
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait, unconfirmed_metadata
from app.db.unconfirmed_session import init_unconfirmed_db

@pytest.fixture(scope="module")
def test_engine():
    test_db_url = "sqlite:///unconfirmed_test.db"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    
    unconfirmed_metadata.create_all(engine)
    
    yield engine
    
    import shutil
    from pathlib import Path
    db_path = Path("unconfirmed_test.db")
    if db_path.exists():
        db_path.unlink()

@pytest.mark.asyncio
async def test_unconfirmed_universe_crud(test_engine):
    with Session(test_engine) as session:
        u = UnconfirmedUniverse(name="Test Universe", summary="A test universe")
        session.add(u)
        session.commit()
        session.refresh(u)
        
        assert u.id is not None
        assert u.name == "Test Universe"
        
        # Test retrieval
        statement = select(UnconfirmedUniverse).where(UnconfirmedUniverse.name == "Test Universe")
        retrieved = session.exec(statement).one()
        assert retrieved.id == u.id

@pytest.mark.asyncio
async def test_unconfirmed_trait_crud(test_engine):
    with Session(test_engine) as session:
        # Create universe first
        u = UnconfirmedUniverse(name="Trait Universe")
        session.add(u)
        session.commit()
        session.refresh(u)
        
        t = UnconfirmedTrait(universe_id=u.id, name="Trait 1", value="Value 1", category="Test")
        session.add(t)
        session.commit()
        session.refresh(t)
        
        assert t.id is not None
        assert t.name == "Trait 1"
        
        # Test retrieval
        statement = select(UnconfirmedTrait).where(UnconfirmedTrait.name == "Trait 1")
        retrieved = session.exec(statement).one()
        assert retrieved.universe_id == u.id
