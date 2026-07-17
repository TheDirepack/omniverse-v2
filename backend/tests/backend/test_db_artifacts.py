import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_artifacts_search(client):
    """Test artifact search functionality"""
    response = client.get("/api/v1/db/artifacts/search?q=test")
    
    assert response.status_code == 200
    data = response.json()
    assert "artifacts" in data
    assert isinstance(data["artifacts"], list)


@pytest.mark.asyncio
async def test_artifacts_search_empty(client):
    """Test artifact search with empty query"""
    response = client.get("/api/v1/db/artifacts/search")
    
    assert response.status_code == 200
    data = response.json()
    assert "artifacts" in data


@pytest.mark.asyncio
async def test_artifacts_get_by_id(client):
    """Test getting artifact by ID"""
    response = client.get("/api/v1/db/artifacts/artifacts/1")
    
    # May not exist yet, just check it doesn't crash
    assert response.status_code in [200, 404]
    
    if response.status_code == 200:
        data = response.json()
        assert "artifact" in data


@pytest.mark.asyncio
async def test_artifacts_list(client):
    """Test listing all artifacts"""
    response = client.get("/api/v1/db/artifacts/artifacts/list")
    
    assert response.status_code == 200
    data = response.json()
    assert "artifacts" in data


@pytest.mark.asyncio
async def test_artifacts_universe_filter(client):
    """Test filtering artifacts by universe"""
    response = client.get("/api/v1/db/artifacts/search?universe=test")
    
    assert response.status_code == 200
    data = response.json()
    assert "artifacts" in data
