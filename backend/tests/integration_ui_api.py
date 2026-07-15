import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.db.session import engine
from app.db.schema import Universe, Artifact, ProviderConfig, ProviderKey, AgentRouteFallback

client = TestClient(app)

def test_artifacts_api(ephemeral_db):
    # Setup: Create a universe and some artifacts
    with Session(ephemeral_db) as session:
        u = Universe(name="Test Universe", slug="test-u")
        session.add(u)
        session.commit()
        
        a1 = Artifact(universe_id=u.id, type="entity", name="Hero A", description="A strong hero")
        a2 = Artifact(universe_id=u.id, type="entity", name="Hero B", description="A fast hero")
        a3 = Artifact(universe_id=u.id, type="world", name="World A", description="A big world")
        session.add_all([a1, a2, a3])
        session.commit()
        u_id = u.id
        a1_id = a1.id

    # 1. Test List
    resp = client.get(f"/api/artifacts/list?universe_id={u_id}")
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    # 2. Test Search
    resp = client.get(f"/api/artifacts/search?universe_id={u_id}&q=strong")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Hero A"

    # 3. Test Details
    resp = client.get(f"/api/artifacts/{a1_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Hero A"

def test_worlds_api_expanded(ephemeral_db):
    # 1. Test expanded creation
    payload = {
        "world_name": "Metadata World",
        "franchise": "Test Franchise",
        "category": "Sci-Fi",
        "continuity": "Main",
        "era": "Future",
        "auto_research": False
    }
    resp = client.post("/api/worlds/create", json=payload)
    assert resp.status_code == 200
    world_id = resp.json()["id"]

    with Session(ephemeral_db) as session:
        w = session.get(Universe, world_id)
        assert w.name == "Metadata World"
        # Verify metadata was created as artifacts
        artifacts = session.exec(select(Artifact).where(Artifact.universe_id == w.id)).all()
        types = [a.type for a in artifacts]
        assert "franchise" in types
        assert "category" in types
        assert "continuity" in types
        assert "era" in types

    # 2. Test Advanced Search
    # Create a few more for filtering
    with Session(ephemeral_db) as session:
        u2 = Universe(name="Other World", franchise="Other")
        session.add(u2)
        session.commit()

    resp = client.get("/api/worlds/search?franchise=Test%20Franchise")
    assert resp.status_code == 200
    # Only Metadata World should match
    assert any(w["name"] == "Metadata World" for w in resp.json())

    # 3. Test Bulk Research
    with Session(ephemeral_db) as session:
        u = session.get(Universe, world_id)
        u_uuid = u.uuid
    
    resp = client.post("/api/worlds/research", json=[u_uuid])
    assert resp.status_code == 200
    assert "run_id" in resp.json()

def test_settings_api_crud(ephemeral_db):
    # 1. Provider Upsert
    provider_payload = {
        "name": "TestProvider",
        "provider_type": "openai",
        "base_url": "http://api.test",
        "models": "gpt-4,gpt-3.5"
    }
    resp = client.post("/api/providers/", json=provider_payload)
    assert resp.status_code == 200
    p_id = resp.json()["id"] if "id" in resp.json() else None # Depending on service impl

    # If service returns success status instead of object, check DB
    with Session(ephemeral_db) as session:
        p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "TestProvider")).first()
        assert p is not None
        p_id = p.id

    # 2. Provider Key Upsert
    key_payload = {
        "provider_id": p_id,
        "api_key": "sk-test-123",
        "priority": 10
    }
    resp = client.post("/api/providers/keys", json=key_payload)
    assert resp.status_code == 200
    
    # 3. Route Upsert
    route_payload = {
        "task_type": "Researcher",
        "provider_id": p_id,
        "models": "gpt-4",
        "priority": 1
    }
    resp = client.post("/api/settings/agent-routes", json=route_payload)
    assert resp.status_code == 200

    # 4. Delete Route
    with Session(ephemeral_db) as session:
        route = session.exec(select(AgentRouteFallback).where(AgentRouteFallback.task_type == "Researcher")).first()
        r_id = route.id
    
    resp = client.delete(f"/api/settings/agent-routes/{r_id}")
    assert resp.status_code == 200

    with Session(ephemeral_db) as session:
        assert session.get(AgentRouteFallback, r_id) is None
