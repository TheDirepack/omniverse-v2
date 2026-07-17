from app.db.schema import Artifact, Universe


def test_knowledge_page(client):
    response = client.get("/knowledge")
    assert response.status_code == 200
    assert "Knowledge - Omniverse" in response.text
    assert "Worlds" in response.text


def test_research_page(client):
    response = client.get("/research")
    assert response.status_code == 200
    assert "Choose a World" in response.text


def test_knowledge_world_list(client, seeded_db):
    _session, u1, _e1, _ = seeded_db
    response = client.get("/knowledge/worlds")
    assert response.status_code == 200
    assert u1.name in response.text


def test_knowledge_world_list_has_artifacts(client, seeded_db):
    _session, u1, _e1, _ = seeded_db
    # U1 has an artifact (E1), so should appear with has_artifacts=true
    response = client.get("/knowledge/worlds", params={"has_artifacts": "true"})
    assert response.status_code == 200
    assert u1.name in response.text


def test_knowledge_world_list_has_artifacts_excludes_empty(client, seeded_db):
    session, u1, _e1, _ = seeded_db
    u2 = Universe(name="EmptyWorld", is_explored=False)
    session.add(u2)
    session.commit()
    # U2 has no artifacts, should NOT appear with has_artifacts=true
    response = client.get("/knowledge/worlds", params={"has_artifacts": "true"})
    assert response.status_code == 200
    assert u1.name in response.text
    assert "EmptyWorld" not in response.text


def test_knowledge_world_list_search(client, seeded_db):
    session, _u1, _e1, _ = seeded_db
    u2 = Universe(name="Zorldo", is_explored=False)
    session.add(u2)
    session.commit()
    response = client.get("/knowledge/worlds", params={"q": "Zor"})
    assert response.status_code == 200
    assert "Zorldo" in response.text
    assert "U1" not in response.text


def test_knowledge_world_list_artifact_count(client, seeded_db):
    session, u1, _e1, _ = seeded_db
    e2 = Artifact(name="E2", type="claim", universe_id=u1.id)
    session.add(e2)
    session.commit()
    response = client.get("/knowledge/worlds")
    assert response.status_code == 200
    # Should show artifact count of 2 (E1 + E2)
    assert "2" in response.text


def test_knowledge_world_detail(client, seeded_db):
    _, u1, _, _ = seeded_db
    response = client.get(f"/knowledge/worlds/{u1.id}")
    assert response.status_code == 200
    assert "U1" in response.text
    assert "Entities" in response.text
    assert "Claims" in response.text


def test_knowledge_world_detail_not_found(client):
    response = client.get("/knowledge/worlds/99999")
    assert response.status_code == 404
    assert "World not found" in response.text


def test_knowledge_entity_detail(client, seeded_db):
    _, _u1, e1, _ = seeded_db
    response = client.get(f"/knowledge/entities/{e1.id}")
    assert response.status_code == 200
    assert e1.name in response.text
    assert "Associated Claims" in response.text


def test_knowledge_entity_detail_not_found(client):
    response = client.get("/knowledge/entities/99999")
    assert response.status_code == 404
    assert "Entity not found" in response.text


# --- Artifact API tests ---

def test_artifact_list_by_universe(client, seeded_db):
    _, u1, _e1, _ = seeded_db
    response = client.get("/api/v1/db/artifacts/list", params={"universe_id": u1.id})
    assert response.status_code == 200
    assert "E1" in response.text


def test_artifact_list_all(client, seeded_db):
    _, _u1, _e1, _ = seeded_db
    response = client.get("/api/v1/db/artifacts/list")
    assert response.status_code == 200
    assert "E1" in response.text


def test_artifact_search_by_universe(client, seeded_db):
    _, u1, _e1, _ = seeded_db
    response = client.get("/api/v1/db/artifacts/search", params={"universe_id": u1.id, "q": "E1"})
    assert response.status_code == 200
    assert "E1" in response.text


def test_artifact_search_global(client, seeded_db):
    _, _u1, _e1, _ = seeded_db
    response = client.get("/api/v1/db/artifacts/search", params={"q": "E1"})
    assert response.status_code == 200
    assert "E1" in response.text


def test_artifact_search_global_no_results(client, seeded_db):
    response = client.get("/api/v1/db/artifacts/search", params={"q": "NONEXISTENT_ARTIFACT_XYZ"})
    assert response.status_code == 200
    assert "No artifacts found" in response.text


def test_artifact_detail(client, seeded_db):
    _, _u1, e1, _ = seeded_db
    response = client.get(f"/api/v1/db/artifacts/{e1.id}")
    assert response.status_code == 200
    assert "E1" in response.text
    assert e1.type in response.text


def test_artifact_detail_not_found(client):
    response = client.get("/api/v1/db/artifacts/99999")
    assert response.status_code == 404
