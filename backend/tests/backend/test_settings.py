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
    response = client.get("/api/v1/settings/providers/list")
    
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data


@pytest.mark.asyncio
async def test_settings_providers_get(client):
    """Test getting provider by ID"""
    response = client.get("/api/v1/settings/providers/get/provider-1")
    
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_settings_providers_update(client):
    """Test updating provider configuration"""
    response = client.put(
        "/api/v1/settings/providers/update/provider-1",
        json={
            "name": "test-provider",
            "base_url": "http://test.com",
            "enabled": True
        }
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_settings_routes_list(client):
    """Test listing agent routes"""
    response = client.get("/api/v1/settings/routes/list")
    
    assert response.status_code == 200
    data = response.json()
    assert "routes" in data


@pytest.mark.asyncio
async def test_settings_general(client):
    """Test general settings"""
    response = client.get("/api/v1/settings/general")
    
    assert response.status_code == 200
    data = response.json()
    assert "settings" in data or "max_agents_per_turn" in data
