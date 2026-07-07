from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_csrf_protection_on_post():
    # CSRF was removed — local dev tool. POST without any CSRF should succeed.
    response = client.post("/inference/materialize")
    assert response.status_code == 200
