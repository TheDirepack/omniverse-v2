import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_runs_start(client):
    """Test starting a new run via /workflow endpoint"""
    response = client.post(
        "/api/v1/execution/runs/workflow",
        json={
            "run_type": "research",
            "world_name": "test-world",
            "min_turns": 3,
            "max_turns": 10,
            "universe_uuids": ["test-uuid"]
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "run_id" in data


@pytest.mark.asyncio
async def test_runs_active_list(client):
    """Test listing active runs (returns HTML template)"""
    response = client.get("/api/v1/execution/runs/active-detailed")

    assert response.status_code == 200
    html = response.text
    # Check for expected content in HTML
    assert "run" in html.lower() or "active" in html.lower()


@pytest.mark.asyncio
async def test_runs_get_by_id(client):
    """Test getting run by ID (returns HTML)"""
    response = client.get("/api/v1/execution/runs/1")

    assert response.status_code in [200, 404]


@pytest.mark.asyncio
async def test_runs_abort_single(client):
    """Test aborting a single run"""
    response = client.post("/api/v1/execution/runs/abort", json={"run_id": 1})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_runs_abort_all(client):
    """Test aborting all active runs"""
    response = client.post("/api/v1/execution/runs/abort-all")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data or "aborted_count" in data


@pytest.mark.asyncio
async def test_runs_tiering(client):
    """Test tiering workflow"""
    response = client.post("/api/v1/execution/runs/tiering")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_runs_extrapolation(client):
    """Test extrapolation workflow"""
    response = client.post(
        "/api/v1/execution/runs/extrapolate",
        json={"scope": "all"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_runs_focused_search(client):
    """Test focused search workflow"""
    response = client.post(
        "/api/v1/execution/runs/focused-search",
        json={
            "query": "power comparison",
            "universe_uuids": ["test-uuid"],
            "features": ["comparison"]
        }
    )

    assert response.status_code == 200
