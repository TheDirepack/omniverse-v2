import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def setup_artifact():
    """Create a test artifact"""
    return {
        "type": "ENTITY",
        "universe": "test-world",
        "content": "Test entity for UI testing",
        "tags": ["test"],
        "is_explored": True,
        "tier": None
    }


@pytest.mark.asyncio
async def test_knowledge_page_loads(client, setup_artifact):
    """Test that knowledge page loads correctly"""
    # First save an artifact
    response = client.post(
        "/api/v1/db/artifacts/save",
        json=setup_artifact
    )
    assert response.status_code == 200
    
    # Now load the knowledge page
    response = client.get("/knowledge")
    
    assert response.status_code == 200
    html = response.text
    assert "Knowledge" in html
    assert "Artifacts" in html


@pytest.mark.asyncio
async def test_knowledge_search_by_universe(client):
    """Test searching artifacts by universe via UI"""
    # Save artifacts with different universes
    client.post("/api/v1/db/artifacts/save", json={
        **setup_artifact,
        "universe": "world-1"
    })
    client.post("/api/v1/db/artifacts/save", json={
        **setup_artifact,
        "universe": "world-2"
    })
    
    # Load knowledge page and verify it can filter
    response = client.get("/knowledge?universe=world-1")
    
    assert response.status_code == 200
    assert "world-1" in response.text.lower()


@pytest.mark.asyncio
async def test_knowledge_notebook_tab(client):
    """Test knowledge notebook tab functionality"""
    # Save some notebook entries
    client.post("/api/v1/db/notebook/save", json={
        "id": f"notebook-{uuid.uuid4()}",
        "content": "Test note content",
        "type": "note",
        "tags": ["test"]
    })
    
    # Load knowledge page with notebook tab
    response = client.get("/knowledge")
    
    assert response.status_code == 200
    assert "Notebook" in response.text


@pytest.mark.asyncio
async def test_artifact_details_page(client):
    """Test artifact details page loads"""
    # First create an artifact
    artifact_data = {
        **setup_artifact,
        "id": f"artifact-{uuid.uuid4()}"
    }
    
    response = client.post("/api/v1/db/artifacts/save", json=artifact_data)
    assert response.status_code == 200
    
    # Get the artifact ID from response
    data = response.json()
    artifact_id = data.get("id", artifact_data["id"])
    
    # Load artifact details page
    response = client.get(f"/knowledge/artifact/{artifact_id}")
    
    assert response.status_code == 200
    assert "Details" in response.text or "Artifact" in response.text
