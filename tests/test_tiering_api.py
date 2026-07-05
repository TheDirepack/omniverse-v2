import pytest
from unittest.mock import AsyncMock, patch
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Setting, WorldTier
from app.api.routers.runs import router
from fastapi.testclient import TestClient

client = TestClient(router)

@pytest.mark.asyncio
async def test_trigger_tiering_endpoint():
    """Test that /tiering returns a run_id and queues the task."""
    # The router has prefix /runs, so the endpoint is /runs/tiering
    with patch("app.api.routers.runs.run_tiering_in_background", new=AsyncMock()) as mock_task:
        response = client.post("/runs/tiering")
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert "status" in data and data["status"] == "started"
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_run_tiering_in_background_execution(seeded_db):
    """Test the background task logic: state preparation and node call."""
    ephemeral_db, u, p, r = seeded_db
    
    # Seed consolidated dataset
    setting = Setting(key="CONSOLIDATED_DATASET", value="Consolidated Test Data")
    ephemeral_db.add(setting)
    ephemeral_db.commit()
    
    # Mark universe as explored
    u.is_explored = True
    ephemeral_db.add(u)
    ephemeral_db.commit()
    
    run_id = "test-tier-run"
    
    from app.api.routers.runs import run_tiering_in_background
    
    with patch("app.agents.nodes.architecture_node", new=AsyncMock()) as mock_node:
        await run_tiering_in_background(run_id)
        
        # Verify architecture_node was called
        mock_node.assert_called_once()
        
        # Check the state passed to the node
        state = mock_node.call_args[0][0]
        assert state["run_id"] == run_id
        assert state["verified_worlds"] == [u.name]
        assert state["active_task"] == "ARCHITECTURE"
        assert state["current_tier_system"] is None
        
    # Verify run was removed from active runs (mocked or real)
    from app.core.runtime_state import ABORTED_RUNS
    assert run_id not in ABORTED_RUNS
