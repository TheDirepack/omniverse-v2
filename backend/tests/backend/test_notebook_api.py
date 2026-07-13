import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.db.notebook_session import notebook_engine
from app.db.notebook_schema import NotebookEntry

client = TestClient(app)

def test_save_notebook_entry(client):
    payload = {
        "universe_name": "Test Universe",
        "items": [
            {
                "title": "Entry 1",
                "summary": "Summary 1",
                "details": "Details 1",
                "kind": "Observation",
                "priority": 1
            }
        ]
    }
    response = client.post("/api/notebook/entries", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_delete_notebook_entry(client):
    # Setup: Create an entry
    with Session(notebook_engine) as session:
        entry = NotebookEntry(
            universe_uuid="test-uuid",
            title="Delete Me",
            summary="Summary",
            kind="Observation"
        )
        session.add(entry)
        session.commit()
        entry_id = entry.id

    response = client.delete(f"/api/notebook/entries/{entry_id}")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]

    with Session(notebook_engine) as session:
        assert session.get(NotebookEntry, entry_id) is None
