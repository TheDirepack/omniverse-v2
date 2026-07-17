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
        "/api/v1/db/notebook/save",
        json={
            "id": "test-123",
            "content": "Test content",
            "type": "note",
            "tags": ["test"]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


@pytest.mark.asyncio
async def test_notebook_update(client):
    """Test updating notebook entry"""
    response = client.put(
        "/api/v1/db/notebook/update/test-123",
        json={"content": "Updated content"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


@pytest.mark.asyncio
async def test_notebook_delete(client):
    """Test deleting notebook entry"""
    response = client.delete("/api/v1/db/notebook/delete/test-123")
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data


@pytest.mark.asyncio
async def test_notebook_get(client):
    """Test getting notebook entry"""
    response = client.get("/api/v1/db/notebook/get/test-123")
    
    assert response.status_code in [200, 404]
