import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import engine
from app.db.schema import ExecutionState
from sqlmodel import Session

client = TestClient(app)

def test_runs_history_invalid_json_state(seeded_db):
    """Verify that runs_history handles invalid JSON in state_snapshot gracefully."""
    with Session(engine) as session:
        # Create a run with invalid JSON state_snapshot
        run = ExecutionState(
            run_id="invalid-json-run",
            status="COMPLETED",
            node_name="Manager",
            thought="Testing invalid JSON",
            state_snapshot="invalid { json : [}",
        )
        session.add(run)
        session.commit()

    response = client.get("/api/runs/history")
    assert response.status_code == 200
    assert "Unknown Goal" in response.text
    assert "invalid-json-run" in response.text

def test_runs_history_none_state_snapshot(seeded_db):
    """Verify that runs_history handles None state_snapshot gracefully."""
    with Session(engine) as session:
        # Create a run with None state_snapshot
        run = ExecutionState(
            run_id="none-state-run",
            status="COMPLETED",
            node_name="Manager",
            thought="Testing None state",
            state_snapshot="{}",
        )
        session.add(run)
        session.commit()

    response = client.get("/api/runs/history")
    assert response.status_code == 200
    assert "Unknown Goal" in response.text
    assert "none-state-run" in response.text

def test_runs_history_valid_json_state(seeded_db):
    """Verify that runs_history correctly parses valid JSON state_snapshot."""
    with Session(engine) as session:
        # Create a run with valid JSON state_snapshot
        run = ExecutionState(
            run_id="valid-json-run",
            status="COMPLETED",
            node_name="Manager",
            thought="Testing valid JSON",
            state_snapshot='{"target_worlds": ["World A", "World B"]}',
        )
        session.add(run)
        session.commit()

    response = client.get("/api/runs/history")
    assert response.status_code == 200
    assert "World A, World B" in response.text
    assert "valid-json-run" in response.text
