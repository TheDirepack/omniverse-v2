import pytest
from sqlmodel import Session, text

from app.db.schema import Universe, UniverseRelation, Entity
from app.db.session import engine


def test_research_page(client):
    response = client.get("/research/")
    assert response.status_code == 200
    assert "Database Worlds" in response.text


def test_research_queue(client):
    response = client.get("/research/queue")
    assert response.status_code == 200
    assert "No active research runs" in response.text


def test_database_worlds_empty(client, clean_db):
    response = client.get("/research/database-worlds")
    assert response.status_code == 200
    assert "0 world(s)" in response.text
    assert "No worlds in database" in response.text


def _fresh_ids(clean_db):
    session = clean_db
    u = Universe(name="TestWorld", is_explored=True)
    session.add(u)
    session.commit()
    session.refresh(u)
    uid = u.id
    session.close()
    return uid


def test_database_worlds_with_worlds(client, clean_db):
    uid = _fresh_ids(clean_db)
    response = client.get("/research/database-worlds")
    assert response.status_code == 200
    assert "1 world(s)" in response.text
    assert "TestWorld" in response.text


def test_database_worlds_filter_by_name(client, clean_db):
    uid = _fresh_ids(clean_db)
    response = client.get("/research/database-worlds", params={"q": "TestWorld"})
    assert response.status_code == 200
    assert "TestWorld" in response.text

    response = client.get("/research/database-worlds", params={"q": "NONEXISTENT"})
    assert response.status_code == 200
    assert 'No worlds matching "NONEXISTENT"' in response.text


def test_database_worlds_filter_explored(client, clean_db):
    session = clean_db

    u1 = Universe(name="ExploredOne", is_explored=True)
    session.add(u1)
    u2 = Universe(name="UnexploredOne", is_explored=False)
    session.add(u2)
    session.commit()

    response = client.get("/research/database-worlds", params={"explored": "yes"})
    assert response.status_code == 200
    assert "ExploredOne" in response.text
    assert "UnexploredOne" not in response.text

    response = client.get("/research/database-worlds", params={"explored": "no"})
    assert response.status_code == 200
    assert "ExploredOne" not in response.text
    assert "UnexploredOne" in response.text


def test_database_worlds_filter_franchise(client, clean_db):
    session = clean_db

    session.add(Universe(name="MarvelHero", franchise="Marvel"))
    session.add(Universe(name="DCHero", franchise="DC"))
    session.commit()

    response = client.get("/research/database-worlds", params={"franchise": "Marvel"})
    assert response.status_code == 200
    assert "MarvelHero" in response.text
    assert "DCHero" not in response.text

    response = client.get("/research/database-worlds", params={"franchise": "dc"})
    assert response.status_code == 200
    assert "DCHero" in response.text
    assert "MarvelHero" not in response.text


def test_database_worlds_toggle_explored(client, clean_db):
    uid = _fresh_ids(clean_db)

    response = client.post(f"/research/worlds/{uid}/toggle-explored")
    assert response.status_code == 200

    response = client.get("/research/database-worlds", params={"explored": "no"})
    assert "TestWorld" in response.text

    response = client.get("/research/database-worlds", params={"explored": "yes"})
    assert "TestWorld" not in response.text


def test_database_worlds_delete(client, clean_db):
    uid = _fresh_ids(clean_db)

    response = client.post(f"/research/worlds/{uid}/delete")
    assert response.status_code == 200
    assert "0 world(s)" in response.text
    assert "TestWorld" not in response.text


def test_database_worlds_add_world(client, clean_db):
    response = client.post("/research/add-world", data={"world_name": "NewTestWorld"})
    assert response.status_code == 200
    assert "NewTestWorld" in response.text


def test_database_worlds_add_world_with_metadata(client, clean_db):
    response = client.post("/research/add-world", data={
        "world_name": "FullMetaWorld",
        "franchise": "TestFranchise",
        "category": "TestCategory",
        "continuity": "TestContinuity",
        "era": "TestEra",
    })
    assert response.status_code == 200
    assert "TestFranchise" in response.text


def test_database_worlds_batch_research(client, clean_db):
    session = clean_db
    for name in ["BatchA", "BatchB", "BatchC"]:
        session.add(Universe(name=name))
    session.commit()

    response = client.post("/research/batch-research", data={"world_names": "BatchA,BatchB"})
    assert response.status_code == 200
    assert "Started research for 2 world(s)" in response.text


def test_database_worlds_focused_search_fragment(client):
    response = client.get("/research/focused-search")
    assert response.status_code == 200
    assert "Focused Search" in response.text
    assert "World Names" in response.text
    assert "Features to Prove/Disprove" in response.text


def test_focused_search_submit_empty(client):
    response = client.post("/research/focused-search", data={"worlds": "TestWorld", "features": ","})
    assert response.status_code == 200
    assert "Provide at least one world and one feature" in response.text


def test_world_row_children(client, clean_db):
    session = clean_db

    u1 = Universe(name="ParentUniverse")
    session.add(u1)
    session.commit()
    session.refresh(u1)
    uid = u1.id

    u2 = Universe(name="ChildUniverse")
    session.add(u2)
    session.commit()
    session.refresh(u2)

    session.add(UniverseRelation(
        from_universe_id=uid, to_universe_id=u2.id, relation_type="contains"
    ))
    session.commit()
    session.close()

    response = client.get(f"/knowledge/worlds/{uid}/children")
    assert response.status_code == 200
    # Returns UniverseRelation objects rendered in world_row template
    assert "mb-2" in response.text
