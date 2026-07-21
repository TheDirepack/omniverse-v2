import re
import uuid as _uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _unique(prefix: str = "t") -> str:
    return f"{prefix}-{_uuid.uuid4().hex[:12]}"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_settings_page_loads(client):
    response = client.get("/settings/")
    assert response.status_code == 200
    assert "Settings" in response.text


def test_providers_tab(client):
    response = client.get("/settings/tab/providers")
    assert response.status_code == 200
    assert "Providers" in response.text


def _active_provider_id(html: str) -> str | None:
    m = re.search(r'<input\s+type="hidden"\s+name="id"\s+value="(\d+)"', html)
    return m.group(1) if m else None


def test_provider_create_and_edit(client):
    name = _unique("prov")
    response = client.post(
        "/settings/providers/upsert",
        data={
            "name": name,
            "provider_type": "openai",
            "base_url": "https://api.openai.com/v1",
            "models": "gpt-4,gpt-3.5",
        },
    )
    assert response.status_code == 200
    assert name in response.text

    provider_id = _active_provider_id(response.text)
    assert provider_id, "Active provider ID not found in response"

    edit_response = client.get(f"/settings/providers/{provider_id}")
    assert edit_response.status_code == 200
    assert name in edit_response.text
    assert "openai" in edit_response.text
    assert "https://api.openai.com/v1" in edit_response.text


def test_provider_delete(client):
    name = _unique("del")
    response = client.post(
        "/settings/providers/upsert",
        data={"name": name},
    )
    assert response.status_code == 200

    provider_id = _active_provider_id(response.text)
    assert provider_id

    delete_response = client.post(
        f"/settings/providers/{provider_id}/delete",
        headers={"HX-Request": "true"},
    )
    assert delete_response.status_code == 200
    assert name not in delete_response.text


def test_add_provider_key(client):
    name = _unique("key")
    response = client.post(
        "/settings/providers/upsert",
        data={"name": name},
    )
    assert response.status_code == 200

    provider_id = _active_provider_id(response.text)
    assert provider_id

    key_response = client.post(
        f"/settings/providers/{provider_id}/keys",
        data={"api_key": "sk-test-key", "priority": 0},
        headers={"HX-Request": "true"},
    )
    assert key_response.status_code == 200


def test_provider_sync(client):
    name = _unique("sync")
    response = client.post(
        "/settings/providers/upsert",
        data={"name": name},
    )
    assert response.status_code == 200

    provider_id = _active_provider_id(response.text)
    assert provider_id

    sync_response = client.post(
        f"/settings/providers/{provider_id}/sync",
        headers={"HX-Request": "true"},
    )
    assert sync_response.status_code != 404


def test_routes_tab(client):
    response = client.get("/settings/tab/routes")
    assert response.status_code == 200
    assert "Agent Routing" in response.text


def test_route_upsert(client):
    task = _unique("TASK")
    route_response = client.post(
        "/settings/routes/upsert",
        data={
            "task_type": task,
            "models": "gpt-4",
            "priority": 0,
        },
        headers={"HX-Request": "true"},
    )
    assert route_response.status_code == 200
    assert task in route_response.text


def test_route_delete(client):
    task = _unique("DEL")
    create_response = client.post(
        "/settings/routes/upsert",
        data={
            "task_type": task,
            "models": "gpt-4",
            "priority": 0,
        },
        headers={"HX-Request": "true"},
    )
    assert create_response.status_code == 200

    match = re.search(
        r"hx-post=\"/settings/routes/(\d+)/delete\"", create_response.text
    )
    assert match, "Route delete button not found in response"
    route_id = match.group(1)
    delete_response = client.post(
        f"/settings/routes/{route_id}/delete",
        headers={"HX-Request": "true"},
    )
    assert delete_response.status_code == 200


def test_general_tab(client):
    response = client.get("/settings/tab/general")
    assert response.status_code == 200


def test_save_general_setting(client):
    response = client.post(
        "/settings/general/update",
        data={"key": "test_key", "value": "test_value"},
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200


def test_health_tab(client):
    response = client.get("/settings/tab/health")
    assert response.status_code == 200
