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
    html = response.text
    assert "artifact" in html.lower() or "data" in html.lower()


@pytest.mark.asyncio
async def test_artifacts_search_empty(client):
    """Test artifact search with minimal query"""
    response = client.get("/api/v1/db/artifacts/search?q=")

    assert response.status_code == 200
    html = response.text
    assert "artifact" in html.lower() or "data" in html.lower()


@pytest.mark.asyncio
async def test_artifacts_get_by_id(client):
    """Test getting artifact by ID"""
    response = client.get("/api/v1/db/artifacts/1")

    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_artifacts_list_json(client):
    """Test listing all artifacts via JSON endpoint"""
    response = client.get("/api/v1/db/artifacts/")

    assert response.status_code == 200
    data = response.json()
    # Returns list directly (may be empty)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_artifacts_universe_filter(client):
    """Test filtering artifacts by universe"""
    response = client.get("/api/v1/db/artifacts/search?universe=test&q=search")

    assert response.status_code == 200
    html = response.text
    assert "artifact" in html.lower() or "data" in html.lower()
