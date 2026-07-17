import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_settings_providers_list(client):
    """Test listing providers"""
    response = client.get("/api/v1/settings/providers/")

    assert response.status_code == 200
    data = response.json()
    # Returns list of providers
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]


@pytest.mark.asyncio
async def test_settings_providers_get(client):
    """Test getting provider by ID"""
    response = client.get("/api/v1/settings/providers/1/models")

    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_settings_providers_update(client):
    """Test updating provider configuration via POST"""
    response = client.post(
        "/api/v1/settings/providers/",
        json={
            "id": 1,
            "name": "test-provider",
            "base_url": "http://test.com",
            "enabled": True
        }
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_settings_routes_list(client):
    """Test listing agent routes"""
    response = client.get("/api/v1/settings/routes/")

    assert response.status_code == 200
    data = response.json()
    # Returns list of routes directly
    assert isinstance(data, list)
    assert len(data) > 0
    assert "task_type" in data[0]


@pytest.mark.asyncio
async def test_settings_general(client):
    """Test general settings"""
    response = client.get("/api/v1/settings/general/")

    assert response.status_code == 200
    data = response.json()
    # Returns dict with general_settings, providers, agent_routes keys
    assert "general_settings" in data
    assert "max_composition_depth" in data["general_settings"]
