import os
import atexit
import pytest
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

# Use temp file so worker threads in TestClient share same DB
TEST_DB_PATH = "/tmp/omniverse_test.db"

@atexit.register
def _cleanup():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def auto_create_db():
    """Autouse: create tables before each test, drop after. Ensures clean slate."""
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def ephemeral_db():
    """Yields a session against the ephemeral DB. Tables already exist from autouse."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client():
    """FastAPI TestClient against app with ephemeral DB."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_db(ephemeral_db):
    """DB with seeded Universe, ProviderConfig, AgentRoute for FK tests."""
    from app.db.schema import Universe, ProviderConfig, AgentRoute

    u = Universe(name="TestUniverse", summary="test summary", is_explored=False)
    ephemeral_db.add(u)
    ephemeral_db.commit()
    ephemeral_db.refresh(u)

    p = ProviderConfig(name="test-provider", provider_type="openai", api_key="sk-test")
    ephemeral_db.add(p)
    ephemeral_db.commit()
    ephemeral_db.refresh(p)

    r = AgentRoute(task_type="RESEARCH", provider_id=p.id, model_name="gpt-4")
    ephemeral_db.add(r)
    ephemeral_db.commit()
    ephemeral_db.refresh(r)

    return ephemeral_db, u, p, r
