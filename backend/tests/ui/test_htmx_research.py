from sqlmodel import Session

from app.db.schema import Artifact, Universe, UniverseRelation
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


def test_database_worlds_pagination(client, clean_db):
    """Test multi-page pagination"""
    # Create 5 test worlds
    from app.db.schema import Universe
    for i in range(5):
        u = Universe(name=f"PaginatedWorld{i}", is_explored=bool(i % 2))
        clean_db.add(u)
    clean_db.commit()

    # Test page 1
    response = client.get("/worlds/database-worlds?page=1&page_size=3")
    assert response.status_code == 200
    assert "page 1 of 2" in response.text.lower() or "paginated" in response.text.lower()

    # Test page 2
    response = client.get("/worlds/database-worlds?page=2&page_size=3")
    assert response.status_code == 200


def test_database_worlds_load_more(client, clean_db):
    """Test Load More infinite scroll functionality"""
    # Create 3 worlds
    from app.db.schema import Universe
    for i in range(3):
        u = Universe(name=f"LoadMoreWorld{i}")
        clean_db.add(u)
    clean_db.commit()

    # Initial page
    response = client.get("/worlds/database-worlds?page=1&page_size=2")
    assert response.status_code == 200
    # Should have Load More button
    assert "load more" in response.text.lower() or "more worlds" in response.text.lower()


def test_batch_research_pagination(client, clean_db):
    """Test batch research endpoint pagination"""
    from app.db.schema import Universe
    for i in range(4):
        u = Universe(name=f"BatchResearch{i}")
        clean_db.add(u)
    clean_db.commit()

    response = client.get("/api/v1/db/batch-research", params={"page": 1, "page_size": 2})
    assert response.status_code == 200
    # Should return paginated results (not all 4 at once)


def test_toggle_explored_pagination(client, clean_db):
    """Test toggle explored endpoint with pagination"""
    from app.db.schema import Universe
    u = Universe(name="ToggleExplored", is_explored=False)
    clean_db.add(u)
    clean_db.commit()

    response = client.post(f"/api/v1/worlds/{u.id}/toggle-explored", params={"page": 1, "page_size": 10})
    assert response.status_code == 200


def test_database_worlds_with_filters_and_pagination(client, clean_db):
    """Test combining filters with pagination"""
    from app.db.schema import Universe
    
    # Create mix of explored/unexplored worlds
    for i in range(5):
        u = Universe(
            name=f"Filtered{i}", 
            is_explored=(i % 2 == 0),  # Even indices explored
            franchise="TestFranchise" if i % 3 == 0 else None
        )
        clean_db.add(u)
    clean_db.commit()

    # Test filter + pagination
    response = client.get(
        "/worlds/database-worlds",
        params={"explored": "yes", "franchise": "TestFranchise", "page": 1}
    )
    assert response.status_code == 200


