from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.v2 import AppConfig, create_app
from app.v2.db import create_sqlite_engine
from app.v2.initialize import initialize
from app.v2.models import Provider, ProviderModel, Route, RouteCandidate


@pytest.mark.integration
def test_app_health_and_world_projection_without_startup_schema_creation(
    isolated_paths: dict[str, Path], tmp_path: Path
) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(
        '[{"id":"w","name":"World","franchise":"F","category":"SF",'
        '"continuity":null,"era":null,"parent":null,"aliases":[],"tags":[]}]',
        encoding="utf-8",
    )
    config = AppConfig(
        database_path=isolated_paths["database"],
        blob_path=isolated_paths["blobs"],
        credentials_path=isolated_paths["credentials"],
        seed_path=seed,
    )
    initialize(
        AppConfig(
            database_path=isolated_paths["database"],
            blob_path=isolated_paths["blobs"],
            credentials_path=isolated_paths["credentials"],
            seed_path=seed,
        ).runtime_config()
    )
    app = create_app(config)
    with TestClient(app) as client:
        assert client.get("/api/v2/health").json() == {"status": "ok"}
        response = client.get("/api/v2/worlds")
    assert response.status_code == 200
    assert response.json() == {
        "items": [{"id": "w", "name": "World", "parent_id": None}],
        "next_cursor": None,
    }


@pytest.mark.integration
def test_research_run_api_contract(
    isolated_paths: dict[str, Path], tmp_path: Path
) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(
        '[{"id":"w","name":"World","franchise":"F","category":"SF",'
        '"continuity":null,"era":null,"parent":null,"aliases":[],"tags":[]}]',
        encoding="utf-8",
    )
    config = AppConfig(
        database_path=isolated_paths["database"],
        blob_path=isolated_paths["blobs"],
        credentials_path=isolated_paths["credentials"],
        seed_path=seed,
    )
    initialize(
        AppConfig(
            database_path=isolated_paths["database"],
            blob_path=isolated_paths["blobs"],
            credentials_path=isolated_paths["credentials"],
            seed_path=seed,
        ).runtime_config()
    )
    app = create_app(config)
    payload = {
        "objective": "Research the world",
        "scope": {"continuity": "primary"},
        "targets": [{"world_id": "w", "objective": "Inventory canon"}],
        "max_attempts": 3,
    }
    with TestClient(app) as client:
        created = client.post(
            "/api/v2/research-runs",
            headers={"Idempotency-Key": "api-create"},
            json=payload,
        )
        assert created.status_code == 202
        run_id = created.json()["id"]
        assert (
            client.post(
                "/api/v2/research-runs",
                headers={"Idempotency-Key": "api-create"},
                json=payload,
            ).json()["id"]
            == run_id
        )
        assert (
            client.post(
                "/api/v2/research-runs",
                headers={"Idempotency-Key": "api-create"},
                json=payload | {"objective": "Different"},
            ).status_code
            == 409
        )

        detail = client.get(f"/api/v2/runs/{run_id}")
        assert detail.status_code == 200
        assert len(detail.json()["steps"]) == 10
        events = client.get(f"/api/v2/runs/{run_id}/events")
        assert events.status_code == 200
        assert events.json()["items"][0]["event_type"] == "RUN_CREATED"
        cancelled = client.post(f"/api/v2/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"
        assert client.post(f"/api/v2/runs/{run_id}/resume").status_code == 409
        assert client.post(f"/api/v2/runs/{run_id}/retry").status_code == 409


@pytest.mark.integration
def test_provider_metadata_and_write_only_credential_api(
    isolated_paths: dict[str, Path],
    tmp_path: Path,
) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(
        '[{"id":"w","name":"World","franchise":"F","category":"SF",'
        '"continuity":null,"era":null,"parent":null,"aliases":[],"tags":[]}]',
        encoding="utf-8",
    )
    initialize(
        AppConfig(
            database_path=isolated_paths["database"],
            blob_path=isolated_paths["blobs"],
            credentials_path=isolated_paths["credentials"],
            seed_path=seed,
        ).runtime_config()
    )
    engine = create_sqlite_engine(isolated_paths["database"])
    with Session(engine) as session, session.begin():
        session.add(Provider(id="openai", kind="OPENAI", base_url=None, active=True))
        session.add(
            ProviderModel(
                id="gpt",
                provider_id="openai",
                model_name="gpt",
                context_window=40_000,
                output_limit=4_000,
                supports_tools=True,
                supports_structured=True,
                supports_text=True,
                active=True,
            )
        )
        session.add(Route(id="research", task="research", position=0, active=True))
        session.add(
            RouteCandidate(
                id="candidate",
                route_id="research",
                model_id="gpt",
                position=0,
                weight=1,
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
    with TestClient(app) as client:
        metadata = client.get("/api/v2/providers")
        assert metadata.status_code == 200
        assert metadata.json()["items"][0]["models"][0]["supports_tools"] is True
        created = client.post(
            "/api/v2/providers/openai/credentials",
            json={"label": "primary", "secret": "sk-api"},
        )
        assert created.status_code == 201
        assert "sk-api" not in created.text
        credential_id = created.json()["credential_id"]
        assert client.get("/api/v2/providers").text.find("sk-api") == -1
        assert (
            client.delete(
                f"/api/v2/providers/openai/credentials/{credential_id}"
            ).status_code
            == 204
        )
