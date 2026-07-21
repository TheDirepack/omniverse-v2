import uuid as uuid_lib

import pytest
from fastapi.testclient import TestClient

from app.db.schema import Universe
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def universe_uuid(session):
    u = Universe(name=f"test-research-{uuid_lib.uuid4().hex[:8]}")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u.uuid


@pytest.mark.asyncio
async def test_research_page_loads(client):
    """Test that research page loads correctly"""
    response = client.get("/research")

    assert response.status_code == 200
    assert "Research" in response.text


@pytest.mark.asyncio
async def test_start_research_workflow(client, universe_uuid):
    """Test starting a research workflow from UI"""
    response = client.post(
        "/api/v1/execution/runs/start",
        json={"payload": [universe_uuid]}
    )

    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data


@pytest.mark.asyncio
async def test_tiering_workflow_from_ui(client):
    """Test tiering workflow via UI"""
    response = client.post("/api/v1/execution/runs/tiering")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_extrapolation_workflow_from_ui(client):
    """Test extrapolation workflow via UI"""
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
async def test_active_runs_management(client, session):
    """Test managing active runs from UI"""
    uuids = []
    for _i in range(2):
        u = Universe(name=f"test-world-{uuid_lib.uuid4().hex[:8]}")
        session.add(u)
        session.commit()
        session.refresh(u)
        uuids.append(u.uuid)

    for uid in uuids:
        client.post(
            "/api/v1/execution/runs/start",
            json={"payload": [uid]}
        )

    response = client.get("/api/v1/execution/runs/active")
    assert response.status_code == 200

    response = client.delete("/api/v1/execution/runs/abort-all")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_research_with_notebook(client, session):
    """Test research workflow with notebook integration"""
    u = Universe(name=f"test-notebook-{uuid_lib.uuid4().hex[:8]}")
    session.add(u)
    session.commit()
    session.refresh(u)

    client.post("/api/v1/db/notebook/save", json={
        "id": f"notebook-{uuid_lib.uuid4()}",
        "content": "Initial research notes",
        "type": "note",
        "tags": ["research"]
    })

    response = client.post(
        "/api/v1/execution/runs/start",
        json={"payload": [u.uuid]}
    )
    assert response.status_code == 200
