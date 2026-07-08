import pytest
from app.db.unconfirmed_session import unconfirmed_engine
from app.db.unconfirmed_schema import UnconfirmedClaim, UnconfirmedUniverse
from sqlmodel import Session

@pytest.fixture
def unconfirmed_data():
    with Session(unconfirmed_engine) as session:
        u = UnconfirmedUniverse(name="Test Universe")
        session.add(u)
        session.commit()
        session.refresh(u)
        
        c = UnconfirmedClaim(universe_id=u.id, subject="Subject", predicate="Predicate", object_val="Object")
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
    response = client.post(f"/validation/claim/{unconfirmed_data.id}/approve")
    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    assert '"showToast": {"value": "Claim approved and promoted", "type": "info"}' in response.headers["HX-Trigger"]
    
    # Verify it's gone from unconfirmed
    with Session(unconfirmed_engine) as session:
        claim = session.get(UnconfirmedClaim, unconfirmed_data.id)
        assert claim is None

def test_reject_claim(client, unconfirmed_data):
    response = client.post(f"/validation/claim/{unconfirmed_data.id}/reject")
    assert response.status_code == 200
    assert "HX-Trigger" in response.headers
    assert '"showToast": {"value": "Claim rejected", "type": "info"}' in response.headers["HX-Trigger"]
    
    # Verify it's gone from unconfirmed
    with Session(unconfirmed_engine) as session:
        claim = session.get(UnconfirmedClaim, unconfirmed_data.id)
        assert claim is None

def test_merge_entity(client):
    response = client.post("/validation/entity/1/merge")
    assert response.status_code == 200
