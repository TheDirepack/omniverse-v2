import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_settings_page_loads(client):
    """Test that settings page loads correctly"""
    response = client.get("/settings")
    
    assert response.status_code == 200
    assert "Settings" in response.text


@pytest.mark.asyncio
async def test_providers_list_view(client):
    """Test viewing providers list in settings"""
    response = client.get("/settings/providers")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_provider_edit_form(client):
    """Test provider edit form"""
    # Test editing a provider
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
async def test_routes_configuration(client):
    """Test route configuration"""
    response = client.get("/settings/routes")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_general_settings(client):
    """Test general settings"""
    response = client.get("/settings/general")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_settings_save_button(client):
    """Test saving settings changes"""
    response = client.post("/api/v1/settings/general/save")
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
