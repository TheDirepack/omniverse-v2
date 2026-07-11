import pytest
from sqlmodel import Session

from app.db.unconfirmed_schema import NotebookEntry, UnconfirmedUniverse
from app.db.unconfirmed_session import unconfirmed_engine


@pytest.fixture
def unconfirmed_data():
    with Session(unconfirmed_engine) as session:
        u = UnconfirmedUniverse(name="Test Universe")
        session.add(u)
        session.commit()
        session.refresh(u)

        c = NotebookEntry(
            universe_uuid=u.uuid,
            title="Subject",
            summary="Object",
            details="Predicate"
        )
        session.add(c)
        session.commit()
        session.refresh(c)
        yield c

        # Cleanup
        session.delete(c)
        session.delete(u)
        session.commit()

def test_validation_page(client):
    response = client.get("/validation/")
    assert response.status_code == 200

def test_approve_claim(client, unconfirmed_data):
    response = client.post(f"/validation/entry/{unconfirmed_data.id}/approve")
    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    assert (
        '"showToast": {"value": "Entry approved and promoted", "type": "info"}'
        in response.headers["HX-Trigger"]
    )

    # Verify it's gone from unconfirmed
    with Session(unconfirmed_engine) as session:
        entry = session.get(NotebookEntry, unconfirmed_data.id)
        assert entry is None

def test_reject_claim(client, unconfirmed_data):
    response = client.post(f"/validation/entry/{unconfirmed_data.id}/reject")
    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    assert (
        '"showToast": {"value": "Entry rejected", "type": "info"}'
        in response.headers["HX-Trigger"]
    )

    # Verify it's gone from unconfirmed
    with Session(unconfirmed_engine) as session:
        entry = session.get(NotebookEntry, unconfirmed_data.id)
        assert entry is None

def test_merge_entity(client):
    response = client.post("/validation/entity/1/merge")
    assert response.status_code == 200
