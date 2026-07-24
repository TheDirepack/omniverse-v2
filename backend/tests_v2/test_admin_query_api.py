from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.v2 import AppConfig, create_app
from app.v2.config import V2Config
from app.v2.initialize import initialize


@pytest.fixture
def client(isolated_paths: dict[str, Path], tmp_path: Path) -> TestClient:
    seed = tmp_path / "seed.json"
    worlds = [
        {
            "id": world_id,
            "name": name,
            "franchise": "F",
            "category": "SF",
            "continuity": None,
            "era": None,
            "parent": None,
            "aliases": [],
            "tags": [],
        }
        for world_id, name in (("alpha", "Alpha World"), ("beta", "Beta"))
    ]
    seed.write_text(json.dumps(worlds), encoding="utf-8")
    initialize(
        V2Config(
            database_path=isolated_paths["database"],
            blob_path=isolated_paths["blobs"],
            credentials_path=isolated_paths["credentials"],
            seed_path=seed,
        )
    )
    app = create_app(
        AppConfig(
            database_path=isolated_paths["database"],
            blob_path=isolated_paths["blobs"],
            credentials_path=isolated_paths["credentials"],
            seed_path=seed,
        )
    )
    with TestClient(app) as value:
        yield value


def test_provider_model_route_crud_health_and_secret_omission(
    client: TestClient,
) -> None:
    assert (
        client.post(
            "/api/v2/providers",
            json={
                "id": "p",
                "kind": "OPENAI_COMPATIBLE",
                "base_url": "https://local.test/v1",
            },
        ).status_code
        == 201
    )
    assert (
        client.patch("/api/v2/providers/p", json={"active": False}).json()["active"]
        is False
    )
    model = client.put(
        "/api/v2/providers/p/models/m",
        json={
            "model_name": "model",
            "context_window": 32000,
            "output_limit": 2000,
            "supports_tools": True,
            "supports_structured": True,
        },
    )
    assert model.status_code == 200
    route = client.put(
        "/api/v2/routes/research.plan",
        json={"candidates": [{"model_id": "m", "weight": 2}]},
    )
    assert route.status_code == 200
    credential = client.post(
        "/api/v2/providers/p/credentials", json={"label": "main", "secret": "secret"}
    )
    assert credential.status_code == 201
    assert "opaque_ref" not in credential.json()
    candidate_id = route.json()["candidates"][0]["id"]
    assert (
        client.post(f"/api/v2/health/candidates/{candidate_id}/reset").status_code
        == 204
    )
    credential_id = credential.json()["credential_id"]
    assert (
        client.post(f"/api/v2/health/credentials/{credential_id}/reset").status_code
        == 204
    )
    settings = client.get("/api/v2/providers").json()
    assert settings["model_discovery"] == "MANUAL_ONLY"
    assert settings["items"][0]["credentials"][0]["health"]["failure_count"] == 0
    assert settings["routes"][0]["health"]["failure_count"] == 0
    assert client.delete("/api/v2/providers/p").status_code == 204


def test_world_search_pagination_run_list_and_projection_endpoints(
    client: TestClient,
) -> None:
    first = client.get("/api/v2/worlds", params={"q": "a", "limit": 1}).json()
    assert len(first["items"]) == 1
    assert first["next_cursor"] is not None
    second = client.get(
        "/api/v2/worlds", params={"q": "a", "limit": 1, "cursor": first["next_cursor"]}
    ).json()
    assert second["items"][0]["id"] != first["items"][0]["id"]
    assert client.get("/api/v2/runs").json() == {"items": [], "next_cursor": None}
    assert client.get("/api/v2/canon", params={"world_id": "alpha"}).status_code == 200
    assert client.get("/api/v2/evidence/alpha").status_code == 200
    assert client.get("/api/v2/evidence", params={"world_id": "alpha"}).json() == {
        "items": [],
        "next_cursor": None,
    }
    assert client.get("/api/v2/provenance/unknown").json() == {"items": []}
    assert client.get("/api/v2/research/none/gaps-conflicts").status_code == 200
    assert (
        client.get(
            "/api/v2/coverage", params={"world_id": "alpha", "continuity": "prime"}
        ).status_code
        == 200
    )
    assert client.get("/api/v2/runs/none/summary").status_code == 404
    assert client.get("/api/v2/runs/none/flow").status_code == 404


def test_research_create_is_accepted(client: TestClient) -> None:
    response = client.post(
        "/api/v2/research-runs",
        headers={"Idempotency-Key": "accepted"},
        json={
            "objective": "Research",
            "scope": {},
            "targets": [{"world_id": "alpha", "objective": "Research"}],
        },
    )
    assert response.status_code == 202
