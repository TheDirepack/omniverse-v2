from fastapi.testclient import TestClient
from app.main import app

def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Omniverse V2" in response.text
    assert "Start Research" in response.text
    assert "Explore Graph" in response.text
    assert "View Rules" in response.text
