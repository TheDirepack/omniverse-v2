import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def setup_world():
    """Create a test world/artifact"""
    return {
        "type": "UNIVERSE",
        "universe": "test-research-world",
        "content": "Test world for research workflow testing",
        "tags": ["research", "test"],
        "is_explored": True,
        "tier": None
    }


@pytest.mark.asyncio
async def test_research_page_loads(client):
    """Test that research page loads correctly"""
    response = client.get("/research")
    
    assert response.status_code == 200
    assert "Research" in response.text


@pytest.mark.asyncio
async def test_start_research_workflow(client, setup_world):
    """Test starting a research workflow from UI"""
    # First create the world artifact
    response = client.post("/api/v1/db/artifacts/save", json=setup_world)
    assert response.status_code == 200
    
    # Start research workflow
    response = client.post(
        "/api/v1/execution/runs/start",
        json={
            "run_type": "research",
            "world_name": "test-research-world",
            "min_turns": 3,
            "max_turns": 10
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "success" in data or "run_id" in data


@pytest.mark.asyncio
async def test_tiering_workflow_from_ui(client):
    """Test tiering workflow via UI"""
    # Start tiering workflow
    response = client.post("/api/v1/execution/runs/tiering")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_extrapolation_workflow_from_ui(client):
    """Test extrapolation workflow via UI"""
    # Start extrapolation workflow
    response = client.post("/api/v1/execution/runs/extrapolation")
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_focused_search_workflow(client):
    """Test focused search workflow from UI"""
    response = client.post(
        "/api/v1/execution/runs/focused-search",
        json={"query": "power comparison"}
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_active_runs_management(client, setup_world):
    """Test managing active runs from UI"""
    # Create multiple runs
    for i in range(2):
        client.post(
            "/api/v1/execution/runs/start",
            json={
                "run_type": "research",
                "world_name": "test-world",
                "min_turns": 3,
                "max_turns": 5
            }
        )
    
    # List active runs
    response = client.get("/api/v1/execution/runs/active")
    assert response.status_code == 200
    
    # Abort all runs
    response = client.delete("/api/v1/execution/runs/abort-all")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_research_with_notebook(client, setup_world):
    """Test research workflow with notebook integration"""
    # Save initial note
    client.post("/api/v1/db/notebook/save", json={
        "id": f"notebook-{uuid.uuid4()}",
        "content": "Initial research notes",
        "type": "note",
        "tags": ["research"]
    })
    
    # Start research
    response = client.post(
        "/api/v1/execution/runs/start",
        json={
            "run_type": "research",
            "world_name": "test-research-world",
            "min_turns": 3
        }
    )
    assert response.status_code == 200
