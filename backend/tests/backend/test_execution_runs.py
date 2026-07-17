import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_runs_start(client):
    """Test starting a new run"""
    response = client.post(
        "/api/v1/execution/runs/start",
        json={
            "run_type": "research",
            "world_name": "test-world",
            "min_turns": 3,
            "max_turns": 10
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data or "error" in data


@pytest.mark.asyncio
async def test_runs_active_list(client):
    """Test listing active runs"""
    response = client.get("/api/v1/execution/runs/active")
    
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data


@pytest.mark.asyncio
async def test_runs_get_by_id(client):
    """Test getting run by ID"""
    response = client.get("/api/v1/execution/runs/get/1")
    
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_runs_abort_single(client):
    """Test aborting a single run"""
    response = client.delete("/api/v1/execution/runs/abort/1")
    
    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_runs_abort_all(client):
    """Test aborting all active runs"""
    response = client.delete("/api/v1/execution/runs/abort-all")
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data or "aborted_count" in data


@pytest.mark.asyncio
async def test_runs_tiering(client):
    """Test tiering workflow"""
    response = client.post("/api/v1/execution/runs/tiering")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_runs_extrapolation(client):
    """Test extrapolation workflow"""
    response = client.post("/api/v1/execution/runs/extrapolation")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_runs_focused_search(client):
    """Test focused search workflow"""
    response = client.post(
        "/api/v1/execution/runs/focused-search",
        json={"query": "power comparison"}
    )
    
    assert response.status_code == 200
