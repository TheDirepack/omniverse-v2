import pytest
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, ExecutionState

def test_focused_search_endpoint_success(client):
    payload = {"worlds": ["World A", "World B"], "features": ["Feature X", "Feature Y"]}
    r = client.post("/api/focused-search", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "started"
    assert "run_id" in data
    assert data["worlds"] == payload["worlds"]
    assert data["features"] == payload["features"]

def test_focused_search_endpoint_validation(client):
    # Missing worlds
    r = client.post("/api/focused-search", json={"features": ["F"]})
    assert r.status_code == 422
    
    # Missing features
    r = client.post("/api/focused-search", json={"worlds": ["W"]})
    assert r.status_code == 422

def test_focused_search_invalid_types(client):
    # Worlds not a list
    r = client.post("/api/focused-search", json={"worlds": "World A", "features": ["F"]})
    assert r.status_code == 422
    
    # Features not a list
    r = client.post("/api/focused-search", json={"worlds": ["W"], "features": "Feature A"})
    assert r.status_code == 422

def test_focused_search_triggers_run_id(client):
    # This test checks if a run_id is returned and if it's a valid UUID (roughly)
    payload = {"worlds": ["W1"], "features": ["F1"]}
    r = client.post("/api/focused-search", json=payload)
    run_id = r.json()["run_id"]
    assert len(run_id) > 10
