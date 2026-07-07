from fastapi.testclient import TestClient
from app.main import app
from app.db.unconfirmed_schema import UnconfirmedClaim, ProvenanceEdge, AcquisitionArtifact, UnconfirmedUniverse
from sqlmodel import Session, select
from app.db.unconfirmed_session import unconfirmed_engine

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

    # 3. Save unconfirmed claim with artifact_id
    payload = {
        "universe_name": universe_name,
        "items": [
            {
                "subject": "Test Subject",
                "context": "Test Context",
                "predicate": "TEST_PRED",
                "object_val": "Test Object",
                "artifact_id": artifact_id
            }
        ]
    }

    resp = client.post("/api/unconfirmed/claims", json=payload)
    if resp.status_code != 200:
        print(f"Error response: {resp.text}")
    assert resp.status_code == 200

    assert "Saved 1 unconfirmed claim(s)" in resp.text

    # 4. Verify claim and provenance
    with Session(unconfirmed_engine) as session:
        claim = session.exec(
            select(UnconfirmedClaim).where(
                UnconfirmedClaim.subject == "Test Subject"
            )
        ).first()
        assert claim is not None

        provenance = session.exec(
            select(ProvenanceEdge).where(
                ProvenanceEdge.target_type == "unconfirmed_claim",
                ProvenanceEdge.target_id == claim.id
            )
        ).first()

        assert provenance is not None
        assert provenance.source_artifact_id == artifact_id
        assert provenance.relation == "supports"
