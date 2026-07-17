import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_notebook_save(client):
    """Test saving notebook entry"""
    response = client.post(
        "/api/v1/db/notebook/entries",
        json={
            "universe_name": "test-world",
            "items": [{
                "title": "Test Entry",
                "summary": "Test summary",
                "kind": "Observation",
                "priority": 0
            }]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


@pytest.mark.asyncio
async def test_notebook_update(client):
    """Test updating notebook entry"""
    response = client.put(
        "/api/v1/db/notebook/entries/1",
        json={
            "title": "Updated Title",
            "summary": "Updated summary",
            "kind": "Observation"
        }
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_notebook_delete(client):
    """Test deleting notebook entry"""
    response = client.delete("/api/v1/db/notebook/entries/1")
    
    assert response.status_code == 200
