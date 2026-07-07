from app.db.schema import Universe, WorldTier
from app.db.session import engine
from app.main import app
from fastapi.testclient import TestClient
from sqlmodel import Session

def test_extrapolate_all_scope(client, clean_db):
    # Setup: Create some verified worlds
    with Session(engine) as session:
        u1 = Universe(name="U1", is_explored=True)
        u2 = Universe(name="U2", is_explored=True)
        u3 = Universe(name="U3", is_explored=False)
        session.add_all([u1, u2, u3])
        session.commit()
        session.refresh(u1)
        session.refresh(u2)

    response = client.post("/api/runs/extrapolate", json={"scope": "all"})
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "U1" in data["worlds"]
    assert "U2" in data["worlds"]
    assert "U3" not in data["worlds"]

def test_extrapolate_worlds_scope(client, clean_db):
    # Setup: Create some verified worlds
    with Session(engine) as session:
        u1 = Universe(name="U1", is_explored=True)
        u2 = Universe(name="U2", is_explored=False)
        session.add_all([u1, u2])
        session.commit()

    response = client.post(
        "/api/runs/extrapolate",
        json={"scope": "worlds", "worlds": ["U1", "U2", "NonExistent"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "worlds" in data
    assert "U1" in data["worlds"]
    assert "U2" not in data["worlds"]
    assert "NonExistent" not in data["worlds"]

def test_extrapolate_worlds_missing_list(client):
    response = client.post("/api/runs/extrapolate", json={"scope": "worlds"})
    assert response.status_code == 400
    assert "worlds list required" in response.json()["detail"]

def test_extrapolate_tier_scope(client, clean_db):
    # Setup: Create worlds and assign them to a tier
    with Session(engine) as session:
        u1 = Universe(name="T1_U1", is_explored=True)
        u2 = Universe(name="T1_U2", is_explored=True)
        u3 = Universe(name="T2_U1", is_explored=True)
        session.add_all([u1, u2, u3])
        session.commit()
        session.refresh(u1)
        session.refresh(u2)
        session.refresh(u3)

        from app.db.schema import TierSystem

        ts = TierSystem(system_definition="Test System")
        session.add(ts)
        session.commit()
        session.refresh(ts)

        wt1 = WorldTier(
            universe_id=u1.id, system_id=ts.id, tier_number=1, justification="J1"
        )
        wt2 = WorldTier(
            universe_id=u2.id, system_id=ts.id, tier_number=1, justification="J2"
        )
        wt3 = WorldTier(
            universe_id=u3.id, system_id=ts.id, tier_number=2, justification="J3"
        )
        session.add_all([wt1, wt2, wt3])
        session.commit()

    response = client.post("/api/runs/extrapolate", json={"scope": "tier", "tier": 1})
    assert response.status_code == 200
    data = response.json()
    assert "T1_U1" in data["worlds"]
    assert "T1_U2" in data["worlds"]
    assert "T2_U1" not in data["worlds"]

def test_extrapolate_tier_missing_value(client):
    response = client.post("/api/runs/extrapolate", json={"scope": "tier"})
    assert response.status_code == 400
    assert "tier value required" in response.json()["detail"]

def test_extrapolate_invalid_scope(client):
    response = client.post("/api/runs/extrapolate", json={"scope": "invalid"})
    assert response.status_code == 422
