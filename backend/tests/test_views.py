

def test_knowledge_page(client):
    response = client.get("/knowledge")
    assert response.status_code == 200
    assert "Knowledge Explorer" in response.text


def test_research_page(client):
    response = client.get("/research")
    assert response.status_code == 200
    assert "Choose a World" in response.text


def test_inference_page(client):
    response = client.get("/inference")
    assert response.status_code == 200
    assert "Inference Rules" in response.text


def test_knowledge_world_list(client, _seeded_db):
    response = client.get("/knowledge/worlds")
    assert response.status_code == 200
    assert "U1" in response.text
    assert "Tier" in response.text


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
