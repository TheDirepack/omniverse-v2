import pytest
from sqlmodel import Session, create_engine, select
from app.db.schema import Universe
from app.services.universe_service import UniverseService
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import engine as main_engine

# Use a temporary sqlite database for tests
TEST_DATABASE_URL = "sqlite:///test_metadata.db"
test_engine = create_engine(TEST_DATABASE_URL)

@pytest.fixture
def session():
    Universe.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    Universe.metadata.drop_all(test_engine)

@pytest.fixture
def client(monkeypatch):
    # Override the engine in app.db.session to use test_engine
    monkeypatch.setattr("app.db.session.engine", test_engine)
    with TestClient(app) as c:
        yield c

def test_universe_model_fields(session):
    u = Universe(
        name="Test World",
        slug="test-world",
        franchise="Test Franchise",
        category="Test Category",
        continuity="Test Continuity",
        era="Test Era",
        summary="Test Summary",
        is_explored=True
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    
    assert u.name == "Test World"
    assert u.slug == "test-world"
    assert u.franchise == "Test Franchise"
    assert u.category == "Test Category"
    assert u.continuity == "Test Continuity"
    assert u.era == "Test Era"
    assert u.summary == "Test Summary"
    assert u.is_explored is True

def test_create_universe_slug_generation(session, monkeypatch):
    monkeypatch.setattr("app.db.session.engine", test_engine)
    service = UniverseService(session=session)
    u = service.create_universe("My Awesome World")
    
    assert u.name == "My Awesome World"
    assert u.slug == "my_awesome_world"

def test_universe_parent_relation(session):
    parent = Universe(name="Parent World", slug="parent")
    session.add(parent)
    session.commit()
    
    child = Universe(name="Child World", slug="child", parent_id=parent.id)
    session.add(child)
    session.commit()
    
    session.refresh(child)
    assert child.parent_id == parent.id

def test_get_worlds_api_fields(client, session):
    u = Universe(
        name="API World",
        slug="api-world",
        franchise="API Franchise",
        category="API Category",
        continuity="API Continuity",
        era="API Era",
        summary="API Summary",
        is_explored=True
    )
    session.add(u)
    session.commit()
    
    response = client.get("/api/worlds/")
    assert response.status_code == 200
    worlds = response.json()
    print(f"DEBUG: Worlds returned by API: {worlds}")
    world = next((w for w in worlds if w["name"] == "API World"), None)
    assert world is not None, f"API World not found in {worlds}"
    assert world["slug"] == "api-world"
    assert world["franchise"] == "API Franchise"
    assert world["category"] == "API Category"
    assert world["continuity"] == "API Continuity"
    assert world["era"] == "API Era"
