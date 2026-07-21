from sqlmodel import Session

from app.db.schema import Universe
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
    return uid



    assert "Started research for 2 world(s)" in response.text


def test_database_worlds_focused_search_fragment(client):
    response = client.get("/research/focused-search")
    assert response.status_code == 200
    assert "Focused Search" in response.text
    assert "World Names" in response.text
    assert "Features to Prove/Disprove" in response.text


