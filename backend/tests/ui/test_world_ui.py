import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def setup_world_artifact():
    """Create a test world artifact"""
    return {
        "type": "UNIVERSE",
        "universe": "test-world-ui",
        "content": "Test world for UI testing",
        "tags": ["ui-test"],
        "is_explored": True,
        "tier": None
    }


@pytest.mark.asyncio
async def test_world_list_page_loads(client, setup_world_artifact):
    """Test that world list page loads correctly"""
    # Create a world first
    response = client.post("/api/v1/db/artifacts/save", json=setup_world_artifact)
    assert response.status_code == 200

    # Load world list page
    response = client.get("/worlds")

    assert response.status_code == 200
    assert "Worlds" in response.text


@pytest.mark.asyncio
async def test_database_worlds_page(client, setup_world_artifact):
    """Test database worlds page"""
    # Create world
    response = client.post("/api/v1/db/artifacts/save", json=setup_world_artifact)
    assert response.status_code == 200

    # Load database worlds page
    response = client.get("/database/worlds")

    assert response.status_code == 200
    assert "Worlds" in response.text


@pytest.mark.asyncio
async def test_world_details_page(client, setup_world_artifact):
    """Test world details page"""
    # Create world
    response = client.post("/api/v1/db/artifacts/save", json=setup_world_artifact)
    assert response.status_code == 200

    # Get world ID from response
    data = response.json()
    world_id = data.get("id", str(uuid.uuid4()))

    # Load world details
    response = client.get(f"/worlds/{world_id}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_world_tiering_via_ui(client, setup_world_artifact):
    """Test tiering a specific world via UI"""
    # Create world
    response = client.post("/api/v1/db/artifacts/save", json=setup_world_artifact)
    assert response.status_code == 200

    # Start tiering for this world
    response = client.post(
        "/api/v1/execution/runs/tiering",
        json={"world_name": "test-world-ui"}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_artifact_list_page(client):
    """Test artifact list page"""
    response = client.get("/knowledge/artifacts/list")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_knowledge_world_detail(client, setup_world_artifact):
    """Test knowledge world detail page"""
    # Create world
    response = client.post("/api/v1/db/artifacts/save", json=setup_world_artifact)
    assert response.status_code == 200

    # Load knowledge world detail
    response = client.get(
        "/knowledge/world-detail/test-world-ui?run_type=research&min_turns=3&max_turns=10"
    )

    assert response.status_code == 200
