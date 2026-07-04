from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.db.session import engine as main_engine
from app.db.schema import Universe, Trait

client = TestClient(app)

def test_get_traits_all():
    with Session(main_engine) as session:
        # Setup some data
        u = session.exec(select(Universe)).first()
        if not u:
            u = Universe(name="TestWorld")
            session.add(u)
            session.commit()
            session.refresh(u)
        
        t = Trait(universe_id=u.id, name="Gravity", value="1g")
        session.add(t)
        session.commit()

    response = client.get("/api/traits")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(item["name"] == "Gravity" for item in data)

def test_get_traits_filtered():
    u1_id = None
    with Session(main_engine) as session:
        import uuid
        name1 = f"World1_{uuid.uuid4()}"
        name2 = f"World2_{uuid.uuid4()}"
        u1 = Universe(name=name1)
        u2 = Universe(name=name2)
        session.add_all([u1, u2])
        session.commit()
        session.refresh(u1)
        session.refresh(u2)
        u1_id = u1.id
        
        t1 = Trait(universe_id=u1.id, name="Trait1", value="Value1")
        t2 = Trait(universe_id=u2.id, name="Trait2", value="Value2")
        session.add_all([t1, t2])
        session.commit()

    response = client.get(f"/api/traits?universe_ids={u1_id}")
    assert response.status_code == 200
    data = response.json()
    assert any(item["name"] == "Trait1" for item in data)
    assert not any(item["name"] == "Trait2" for item in data)

def test_get_traits_empty():
    response = client.get("/api/traits?universe_ids=999999")
    assert response.status_code == 200
    assert response.json() == []

