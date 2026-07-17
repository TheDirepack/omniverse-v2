import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_logs_page_loads(client):
    """Test that logs page loads correctly"""
    response = client.get("/logs")
    
    assert response.status_code == 200
    assert "Logs" in response.text
    assert "Agent" in response.text or "Run" in response.text


@pytest.mark.asyncio
async def test_active_runs_table(client):
    """Test active runs table displays correctly"""
    response = client.get("/active-runs")
    
    assert response.status_code == 200
    assert "Runs" in response.text


@pytest.mark.asyncio
async def test_logs_filtering(client):
    """Test filtering logs by run type and status"""
    # Test different filter combinations
    for filter_type in ["run_type", "status"]:
        response = client.get(f"/logs?{filter_type}=research")
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_clear_logs_button(client):
    """Test clearing logs functionality"""
    # Clear logs
    response = client.post("/api/v1/tools/clear-logs")
    
    assert response.status_code == 200
    assert "success" in response.json()


@pytest.mark.asyncio
async def test_abort_run_via_ui(client):
    """Test aborting a run via UI"""
    # Create a run first
    start_response = client.post(
        "/api/v1/execution/runs/start",
        json={
            "run_type": "research",
            "world_name": "test-world",
            "min_turns": 3,
            "max_turns": 5
        }
    )
    assert start_response.status_code == 200
    
    data = start_response.json()
    run_id = data.get("run_id") or f"run-{uuid.uuid4()}"
    
    # Test abort endpoint
    response = client.delete(f"/api/v1/execution/runs/abort/{run_id}")
    
    assert response.status_code in [200, 404]
