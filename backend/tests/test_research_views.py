from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_research_page_redirect_no_cookie():
    # No active_world_id cookie set
    response = client.get("/research/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/research/choose-world"

def test_research_page_redirect_invalid_world():
    # Set invalid active_world_id cookie
    client.cookies.set("active_world_id", "non-existent-uuid")
    response = client.get("/research/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/research/choose-world"

def test_research_page_success(api_client):
    # Create a world and set it as active
    from app.services.universe_service import UniverseService
    svc = UniverseService()
    world = svc.create_universe(name="Test Research World")

    api_client.cookies.set("active_world_id", world.uuid)
    response = api_client.get("/research/")
    assert response.status_code == 200
    assert "Test Research World" in response.text
