from sqlmodel import Session

from app.db.schema import Universe, UniverseRelation
from app.db.session import engine


def test_research_page(client):
    from sqlmodel import select

    from app.db.schema import Universe

    with Session(engine) as session:
        u = session.exec(select(Universe)).first()
        if not u:
            u = Universe(name="TestWorld")
            session.add(u)
            session.commit()
            session.refresh(u)
        world_uuid = u.uuid

    response = client.get("/research/", cookies={"active_world_id": world_uuid})
    assert response.status_code == 200
    assert "Research - Omniverse" in response.text




def test_research_queue(client):
    response = client.get("/research/queue")
    assert response.status_code == 200
    assert "No active research runs" in response.text


def test_database_worlds_empty(client, clean_db):
    response = client.get("/worlds/database-worlds")
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
    _ = _fresh_ids(clean_db)
    response = client.get("/worlds/database-worlds")
    assert response.status_code == 200
    assert "1 world(s)" in response.text
    assert "TestWorld" in response.text


def test_database_worlds_filter_by_name(client, clean_db):
    _ = _fresh_ids(clean_db)
    response = client.get("/worlds/database-worlds", params={"q": "TestWorld"})
    assert response.status_code == 200
    assert "TestWorld" in response.text

    response = client.get("/worlds/database-worlds", params={"q": "NONEXISTENT"})
    assert response.status_code == 200
    assert 'No worlds matching "NONEXISTENT"' in response.text


def test_database_worlds_filter_explored(client, clean_db):
    session = clean_db

    u1 = Universe(name="ExploredOne", is_explored=True)
    session.add(u1)
    u2 = Universe(name="UnexploredOne", is_explored=False)
    session.add(u2)
    session.commit()

    response = client.get("/worlds/database-worlds", params={"explored": "yes"})
    assert response.status_code == 200
    assert "ExploredOne" in response.text
    assert "UnexploredOne" not in response.text

    response = client.get("/worlds/database-worlds", params={"explored": "no"})
    assert response.status_code == 200
    assert "ExploredOne" not in response.text
    assert "UnexploredOne" in response.text


def test_database_worlds_filter_franchise(client, clean_db):
    session = clean_db

    session.add(Universe(name="MarvelHero"))
    session.add(Universe(name="DCHero"))
    session.commit()

    response = client.get("/worlds/database-worlds", params={"franchise": "Marvel"})
    assert response.status_code == 200
    assert "MarvelHero" in response.text
    assert "DCHero" not in response.text

    response = client.get("/worlds/database-worlds", params={"franchise": "dc"})
    assert response.status_code == 200
    assert "DCHero" in response.text
    assert "MarvelHero" not in response.text


def test_database_worlds_toggle_explored(client, clean_db):
    uid = _fresh_ids(clean_db)

    response = client.post(f"/worlds/{uid}/toggle-explored")
    assert response.status_code == 200

    response = client.get("/worlds/database-worlds", params={"explored": "no"})
    assert "TestWorld" in response.text

    response = client.get("/worlds/database-worlds", params={"explored": "yes"})
    assert "TestWorld" not in response.text


def test_database_worlds_delete(client, clean_db):
    uid = _fresh_ids(clean_db)

    response = client.post(f"/worlds/{uid}/delete")
    assert response.status_code == 200
    assert "0 world(s)" in response.text
    assert "TestWorld" not in response.text


def test_database_worlds_add_world(client, clean_db):
    response = client.post("/worlds/create", json={"world_name": "NewTestWorld"})
    assert response.status_code == 200
    assert "NewTestWorld" in response.text


def test_database_worlds_add_world_with_metadata(client, clean_db):
    response = client.post("/worlds/create", json={
        "world_name": "FullMetaWorld",
        "franchise": "TestFranchise",
        "category": "TestCategory",
        "continuity": "TestContinuity",
        "era": "TestEra",
    })
    assert response.status_code == 200
    assert "FullMetaWorld" in response.text


def test_database_worlds_batch_research(client, clean_db):
    session = clean_db
    for name in ["BatchA", "BatchB", "BatchC"]:
        session.add(Universe(name=name))
    session.commit()

    response = client.post(
        "/worlds/batch-research", data={"world_names": "BatchA,BatchB"}
    )
    assert response.status_code == 200
    assert "Started research for 2 world(s)" in response.text


def test_database_worlds_focused_search_fragment(client):
    response = client.get("/research/focused-search")
    assert response.status_code == 200
    assert "Focused Search" in response.text
    assert "World Names" in response.text
    assert "Features to Prove/Disprove" in response.text


def test_focused_search_submit_empty(client):
    response = client.post(
        "/research/focused-search", data={"worlds": "TestWorld", "features": ","}
    )
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
