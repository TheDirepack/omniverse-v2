import pytest
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Universe, Trait
from app.db.unconfirmed_session import engine as unconfirmed_engine
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait

def test_get_traits_filtering(client):
    # Setup: create two worlds and traits for one
    with Session(engine) as session:
        u1 = Universe(name="World1", summary="S1", is_explored=True)
        u2 = Universe(name="World2", summary="S2", is_explored=True)
        session.add_all([u1, u2])
        session.commit()
        
        u1_id = u1.id
        u2_id = u2.id
        
        t1 = Trait(universe_id=u1_id, name="T1", value="V1", category="C1")
        t2 = Trait(universe_id=u1_id, name="T2", value="V2", category="C1")
        session.add_all([t1, t2])
        session.commit()

    # Test all traits
    r_all = client.get("/api/traits")
    assert r_all.status_code == 200
    assert len(r_all.json()) == 2

    # Test filtered traits (only World 1)
    r_filtered = client.get(f"/api/traits?universe_ids={u1_id}")
    assert r_filtered.status_code == 200
    assert len(r_filtered.json()) == 2

    # Test filtered traits (only World 2 - empty)
    r_empty = client.get(f"/api/traits?universe_ids={u2_id}")
    assert r_empty.status_code == 200
    assert len(r_empty.json()) == 0


def test_get_unconfirmed_traits_filtering(client):
    # Setup: create unconfirmed universes first
    with Session(unconfirmed_engine) as session:
        uu1 = UnconfirmedUniverse(name="World1")
        uu2 = UnconfirmedUniverse(name="World2")
        session.add_all([uu1, uu2])
        session.commit()
        
        uu1_id = uu1.id
        uu2_id = uu2.id

        ut1 = UnconfirmedTrait(universe_id=uu1_id, name="UT1", value="UV1", category="C1", confidence="0.8")
        ut2 = UnconfirmedTrait(universe_id=uu1_id, name="UT2", value="UV2", category="C1", confidence="0.7")
        ut3 = UnconfirmedTrait(universe_id=uu2_id, name="UT3", value="UV3", category="C1", confidence="0.9")
        session.add_all([ut1, ut2, ut3])
        session.commit()

    # Test all unconfirmed
    r_all = client.get("/api/traits/unconfirmed")
    assert r_all.status_code == 200
    assert len(r_all.json()) == 3

    # Test filtered (only World 1)
    r_filtered = client.get("/api/traits/unconfirmed?universe_ids=World1")
    assert r_filtered.status_code == 200
    assert len(r_filtered.json()) == 2
    assert all(t["universe_name"] == "World1" for t in r_filtered.json()) # This will fail because the API returns UnconfirmedTrait objects which might not have universe_name

    # Test filtered (only World 2)
    r_filtered2 = client.get("/api/traits/unconfirmed?universe_ids=World2")
    assert r_filtered2.status_code == 200
    assert len(r_filtered2.json()) == 1
    assert r_filtered2.json()[0]["universe_name"] == "World2"
