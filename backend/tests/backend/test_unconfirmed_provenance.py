from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.unconfirmed_schema import (
    AcquisitionArtifact,
    NotebookEntry,
    ProvenanceEdge,
    UnconfirmedUniverse,
)
from app.db.unconfirmed_session import unconfirmed_engine
from app.main import app

client = TestClient(app)

def test_save_unconfirmed_claim_with_provenance():
    # 1. Setup an artifact in the unconfirmed DB
    with Session(unconfirmed_engine) as session:
        artifact = AcquisitionArtifact(
            content_hash="test_hash",
            source_url="https://test.com",
            content_type="text/plain",
            extracted_text="test content",
            engine_name="test_engine"
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        artifact_id = artifact.id

    # 2. Setup a universe in unconfirmed DB
    with Session(unconfirmed_engine) as session:
        universe = session.exec(select(UnconfirmedUniverse)).first()
        if not universe:
            universe = UnconfirmedUniverse(name="TestUniverse")
            session.add(universe)
            session.commit()
            session.refresh(universe)
        universe_name = universe.name

    # 3. Save unconfirmed entry with artifact_id
    payload = {
        "universe_name": universe_name,
        "items": [
            {
                "title": "Test Subject",
                "summary": "Test Context",
                "details": "Test Object",
                "artifact_id": artifact_id
            }
        ]
    }

    resp = client.post("/api/unconfirmed/entries", json=payload)
    if resp.status_code != 200:
        print(f"Error response: {resp.text}")
    assert resp.status_code == 200

    assert "success" in resp.text

    # 4. Verify entry and provenance
    with Session(unconfirmed_engine) as session:
        entry = session.exec(
            select(NotebookEntry).where(
                NotebookEntry.title == "Test Subject"
            )
        ).first()
        assert entry is not None

        provenance = session.exec(
            select(ProvenanceEdge).where(
                ProvenanceEdge.target_type == "notebook_entry",
                ProvenanceEdge.target_id == entry.id
            )
        ).first()

        assert provenance is not None
        assert provenance.source_artifact_id == artifact_id
        assert provenance.relation == "supports"
