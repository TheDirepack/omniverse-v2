import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_universes_invalid_limit():
    response = client.get("/api/v1/db/worlds/?limit=0")
    assert response.status_code == 422 # FastAPI validation should catch this

def test_list_universes_invalid_offset():
    response = client.get("/api/v1/db/worlds/?offset=-1")
    assert response.status_code == 422

def test_get_universe_invalid_uuid():
    # Assuming the route is /api/v1/db/worlds/{id}
    # It should return 404 if not found
    response = client.get("/api/v1/db/worlds/999999")
    assert response.status_code == 404 # Should be handled

def test_create_universe_missing_required_fields():
    # Based on the create_universe signature, name is required
    response = client.post("/api/v1/db/worlds/", json={})
    assert response.status_code == 422
