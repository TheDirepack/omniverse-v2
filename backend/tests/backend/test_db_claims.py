import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_claims_get_by_id(client):
    """Test getting claim by ID"""
    response = client.get("/api/v1/db/claims/claims/1")
    
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_claims_list(client):
    """Test listing all claims"""
    response = client.get("/api/v1/db/claims/claims/list")
    
    assert response.status_code == 200
    data = response.json()
    assert "claims" in data


@pytest.mark.asyncio
async def test_claims_universe_filter(client):
    """Test filtering claims by universe"""
    response = client.get("/api/v1/db/claims/claims?universe=test")
    
    assert response.status_code == 200
    data = response.json()
    assert "claims" in data
