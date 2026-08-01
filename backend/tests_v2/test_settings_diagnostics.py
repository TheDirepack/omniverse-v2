from __future__ import annotations

import asyncio
import json
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.v2 import AppConfig, create_app
from app.v2.api import read_log_page
from app.v2.initialize import initialize
from app.v2.models import (
    CandidateHealth,
    CredentialRef,
    Provider,
    ProviderModel,
    Route,
    RouteCandidate,
    RuntimeSetting,
)
from app.v2.providers import (
    ErrorClass,
    ModelResponse,
    OpenRouterAdapter,
    ProviderError,
    Usage,
)
from app.v2.runtime import V2Runtime
from app.v2.views import settings_provider_sync


@pytest.fixture
def diagnostics_client(isolated_paths: dict[str, Path], tmp_path: Path) -> TestClient:
    seed = tmp_path / "worlds.json"
    seed.write_text(
        '[{"id":"w","name":"World","franchise":"F","category":"SF",'
        '"continuity":null,"era":null,"parent":null,"aliases":[],"tags":[]}]',
        encoding="utf-8",
    )
    config = replace(
        AppConfig(
            database_path=isolated_paths["database"],
            blob_path=isolated_paths["blobs"],
            credentials_path=isolated_paths["credentials"],
            seed_path=seed,
        ).runtime_config(),
        logging_root=tmp_path / "logging-root",
    )
    initialize(config)
    runtime = V2Runtime.build(config, adapters={})
    with TestClient(create_app(runtime=runtime, start_worker=False)) as client:
        yield client


def test_settings_tabs_have_exact_order_and_logging_is_not_on_general(
    diagnostics_client: TestClient,
) -> None:
    page = diagnostics_client.get("/settings/")
    assert re.findall(r'<button role="tab"[^>]*>([^<]+)</button>', page.text) == [
        "General",
        "Providers",
        "Models",
        "Routes",
        "Health",
        "Logs",
    ]

    general = diagnostics_client.get("/settings/tab/general")
    assert 'name="log_enabled"' not in general.text
    assert 'name="log_path"' not in general.text
    assert 'name="brave_search_api_key"' in general.text


def test_general_settings_store_brave_search_key_write_only(
    diagnostics_client: TestClient,
) -> None:
    response = diagnostics_client.post(
        "/settings/brave-search", data={"brave_search_api_key": "brave-secret"}
    )

    assert response.status_code == 200
    assert "brave-secret" not in response.text
    assert "Configured" in response.text
    runtime = diagnostics_client.app.state.runtime
    with Session(runtime.engine) as session:
        provider = session.get(Provider, "brave-search")
        credential = session.scalar(
            __import__("sqlalchemy").select(CredentialRef).where(
                CredentialRef.provider_id == "brave-search"
            )
        )
    assert provider is not None and provider.kind == "BRAVE_SEARCH"
    assert credential is not None


def test_preprocessor_settings_reconfigure_all_live_consumers(
    diagnostics_client: TestClient,
) -> None:
    runtime = diagnostics_client.app.state.runtime

    disabled = diagnostics_client.post("/settings/general", data={})
    assert disabled.status_code == 200
    assert runtime.config.preprocessor_enabled is False
    assert runtime.preprocessor is None
    assert runtime.acquisition.preprocessor is None
    assert runtime.workflow.preprocessor is None

    enabled = diagnostics_client.post(
        "/settings/general", data={"preprocessor_enabled": "true"}
    )
    assert enabled.status_code == 200
    assert runtime.config.preprocessor_enabled is True
    assert runtime.preprocessor is runtime.acquisition.preprocessor
    assert runtime.preprocessor is runtime.workflow.preprocessor

    configured = diagnostics_client.post(
        "/settings/preprocessor/save-config",
        data={
            "preprocessor_ssh_host": "gpu.example.test",
            "preprocessor_ssh_user": "operator",
            "preprocessor_ssh_port": "2222",
            "preprocessor_config_path": "/srv/minicpm/config.json",
            "preprocessor_remote_script": "/srv/minicpm/start.sh",
            "preprocessor_pgrep_pattern": "llama-server",
            "preprocessor_base_url": "http://gpu.example.test:8080",
            "preprocessor_model": "MiniCPM-test",
            "preprocessor_timeout_seconds": "4",
            "preprocessor_concurrency": "1",
        },
    )
    assert configured.status_code == 200
    assert runtime.config.preprocessor_base_url == "http://gpu.example.test:8080"
    assert runtime.preprocessor.base_url == "http://gpu.example.test:8080"
    assert runtime.preprocessor.model == "MiniCPM-test"


def test_preprocessor_remote_output_is_html_escaped(
    diagnostics_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.v2.preprocessor_ssh as ssh_module

    class HostileSSH:
        def __init__(self, *_args):
            pass

        def start_server(self):
            return False, '<script>alert("start")</script>'

        def fetch_model_name(self):
            return '<img src=x onerror=alert("model")>'

    monkeypatch.setattr(ssh_module, "PreprocessorSSH", HostileSSH)
    started = diagnostics_client.post("/settings/preprocessor/start")
    model = diagnostics_client.post("/settings/preprocessor/fetch-model")

    assert "<script>" not in started.text
    assert "&lt;script&gt;" in started.text
    assert "<img" not in model.text
    assert "&lt;img" in model.text


def test_logs_form_defaults_apply_immediately_persist_and_disable(
    diagnostics_client: TestClient,
) -> None:
    tab = diagnostics_client.get("/settings/tab/logs")
    assert tab.status_code == 200
    assert 'name="enabled"' in tab.text
    assert "checked" in tab.text
    for field in (
        "folder",
        "server_level",
        "agent_level",
        "server_max_bytes",
        "agent_max_bytes",
        "server_backup_count",
        "agent_backup_count",
    ):
        assert f'name="{field}"' in tab.text
    assert 'hx-post="/settings/logging"' in tab.text
    assert "Effective folder" in tab.text
    assert "Last error" in tab.text

    values = {
        "enabled": "true",
        "folder": "diagnostics",
        "server_level": "WARNING",
        "agent_level": "DEBUG",
        "server_max_bytes": "4096",
        "agent_max_bytes": "8192",
        "server_backup_count": "2",
        "agent_backup_count": "3",
    }
    response = diagnostics_client.post("/settings/logging", data=values)
    assert response.status_code == 200
    runtime = diagnostics_client.app.state.runtime
    assert runtime.server_logger.settings.folder == "diagnostics"
    assert runtime.server_logger.settings.agent_level == "DEBUG"
    with Session(runtime.engine) as session:
        assert session.get(RuntimeSetting, "logging").value_json["folder"] == (
            "diagnostics"
        )

    values.pop("enabled")
    disabled = diagnostics_client.post("/settings/logging", data=values)
    assert disabled.status_code == 200
    assert runtime.server_logger.settings.enabled is False
    assert "Logging disabled" in disabled.text


def test_logs_form_rejects_unsafe_folder_with_useful_safe_error(
    diagnostics_client: TestClient,
) -> None:
    response = diagnostics_client.post(
        "/settings/logging",
        data={
            "enabled": "true",
            "folder": "../../etc",
            "server_level": "INFO",
            "agent_level": "INFO",
            "server_max_bytes": "4096",
            "agent_max_bytes": "4096",
            "server_backup_count": "1",
            "agent_backup_count": "1",
        },
    )
    assert response.status_code == 422
    assert "relative" in response.text or "traversal" in response.text
    assert "/etc/passwd" not in response.text


def test_logging_api_get_put_and_strict_validation(
    diagnostics_client: TestClient,
) -> None:
    current = diagnostics_client.get("/api/v2/settings/logging")
    assert current.status_code == 200
    body = current.json()
    assert body["config"]["enabled"] is True
    assert body["health"]["folder"] == body["effective_folder"]

    payload = body["config"] | {
        "enabled": False,
        "folder": "api-logs",
        "server_level": "ERROR",
    }
    updated = diagnostics_client.put("/api/v2/settings/logging", json=payload)
    assert updated.status_code == 200
    assert updated.json()["config"]["enabled"] is False
    assert diagnostics_client.app.state.runtime.server_logger.settings.folder == (
        "api-logs"
    )
    assert (
        diagnostics_client.put(
            "/api/v2/settings/logging", json=payload | {"unexpected": True}
        ).status_code
        == 422
    )
    assert (
        diagnostics_client.put(
            "/api/v2/settings/logging", json=payload | {"enabled": "false"}
        ).status_code
        == 422
    )
    assert (
        diagnostics_client.put(
            "/api/v2/settings/logging", json=payload | {"folder": "../escape"}
        ).status_code
        == 422
    )


def test_log_api_and_viewer_are_separate_newest_first_escaped_and_malformed_safe(
    diagnostics_client: TestClient,
) -> None:
    logger = diagnostics_client.app.state.runtime.server_logger
    logger.log_event("server", "INFO", "first", "test", "older")
    logger.log_event("server", "ERROR", "second", "test", "<script>alert(1)</script>")
    logger.log_agent("research", "agent.only", message="agent message")
    server_path = Path(logger.health()["folder"]) / "server.jsonl"
    with server_path.open("a", encoding="utf-8") as handle:
        handle.write("not-json<script>alert(2)</script>\n")

    response = diagnostics_client.get(
        "/api/v2/logs/server", params={"level": "ERROR", "search": "script"}
    )
    assert response.status_code == 200
    assert any(
        item["message"] == "<script>alert(1)</script>"
        for item in response.json()["items"]
    )
    assert diagnostics_client.get("/api/v2/logs/access").status_code == 422
    assert (
        diagnostics_client.get(
            "/api/v2/logs/server", params={"search": "x" * 201}
        ).status_code
        == 422
    )

    all_server = diagnostics_client.get("/api/v2/logs/server").json()["items"]
    malformed_index = next(
        index for index, item in enumerate(all_server) if item["malformed"] is True
    )
    second_index = next(
        index for index, item in enumerate(all_server) if item["event_type"] == "second"
    )
    assert malformed_index < second_index
    assert all(item.get("stream") != "agent" for item in all_server)
    agent = diagnostics_client.get("/api/v2/logs/agent").json()["items"]
    assert any(item["message"] == "agent message" for item in agent)

    html = diagnostics_client.get("/settings/logs/view", params={"stream": "server"})
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html.text
    assert "<script>alert(1)</script>" not in html.text
    assert "not-json&lt;script&gt;alert(2)&lt;/script&gt;" not in html.text
    assert "Malformed JSONL entry" in html.text


def test_log_cursor_pagination_has_no_duplicates(
    diagnostics_client: TestClient,
) -> None:
    logger = diagnostics_client.app.state.runtime.server_logger
    for index in range(5):
        logger.log_event("server", "INFO", f"page-{index}", "test", str(index))

    first = diagnostics_client.get("/api/v2/logs/server", params={"limit": 2}).json()
    second = diagnostics_client.get(
        "/api/v2/logs/server",
        params={"limit": 2, "cursor": first["next_cursor"]},
    ).json()
    first_ids = {item["event_id"] for item in first["items"]}
    second_ids = {item["event_id"] for item in second["items"]}
    assert first_ids.isdisjoint(second_ids)
    assert [item["event_type"] for item in first["items"]] == ["page-4", "page-3"]


def test_log_pagination_uses_aggregate_logger_interface_without_duplicates() -> None:
    class RotatedLoggerInterface:
        def __init__(self) -> None:
            self.lines = [
                f'{{"event_id":"{index}","level":"INFO","message":"event {index}"}}'
                for index in range(6)
            ]

        def read_log(self, stream: str, cursor: int = 0, limit: int = 100, **_):
            assert stream == "server"
            return {
                "lines": self.lines[cursor : cursor + limit],
                "next_cursor": min(cursor + limit, len(self.lines)),
                "total_lines": len(self.lines),
            }

    logger = RotatedLoggerInterface()
    first = read_log_page(logger, "server", limit=3)
    second = read_log_page(logger, "server", cursor=first["next_cursor"], limit=3)

    assert [item["event_id"] for item in first["items"]] == ["5", "4", "3"]
    assert [item["event_id"] for item in second["items"]] == ["2", "1", "0"]


def test_log_level_filter_matches_parsed_level_not_message_text(
    diagnostics_client: TestClient,
) -> None:
    logger = diagnostics_client.app.state.runtime.server_logger
    logger.log_event("server", "INFO", "info", "test", "mentions ERROR only")
    logger.log_event("server", "ERROR", "error", "test", "actual error")

    items = diagnostics_client.get(
        "/api/v2/logs/server", params={"level": "ERROR"}
    ).json()["items"]

    assert [item["event_type"] for item in items] == ["error"]


def test_settings_logs_has_only_two_streams_and_no_clear_action(
    diagnostics_client: TestClient,
) -> None:
    tab = diagnostics_client.get("/settings/tab/logs")
    assert '<option value="server">Server</option>' in tab.text
    assert '<option value="agent">Agent</option>' in tab.text
    assert '<option value="access">' not in tab.text
    assert '<option value="error">' not in tab.text
    assert "Clear Logs" not in tab.text
    assert "/settings/logs/clear" not in tab.text


@pytest.mark.asyncio
async def test_provider_sync_releases_database_connection_before_await(
    isolated_paths: dict[str, Path], tmp_path: Path
) -> None:
    seed = tmp_path / "worlds.json"
    seed.write_text("[]", encoding="utf-8")
    config = AppConfig(
        database_path=isolated_paths["database"],
        blob_path=isolated_paths["blobs"],
        credentials_path=isolated_paths["credentials"],
        seed_path=seed,
    ).runtime_config()
    initialize(config)
    runtime = V2Runtime.build(config, adapters={})
    with Session(runtime.engine) as session, session.begin():
        session.add(Provider(id="sync-provider", kind="OPENAI", active=True))
    runtime.credentials.add("sync-provider", "primary", "secret")

    class SyncAdapter:
        called = False

        async def sync_models(self, credential: str) -> list[dict[str, object]]:
            self.called = True
            assert credential == "secret"
            assert runtime.engine.pool.checkedout() == 0
            return [{"id": "synced-model", "name": "Synced display name"}]

    adapter = SyncAdapter()
    runtime.provider_router.adapters["sync-provider"] = adapter
    app = FastAPI()
    app.state.runtime = runtime
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": "/settings/providers/sync-provider/sync-models",
            "query_string": b"",
            "headers": [],
            "app": app,
        }
    )

    response = await settings_provider_sync(request, "sync-provider")

    assert response.status_code == 200
    assert adapter.called is True
    with Session(runtime.engine) as session:
        model = session.get(ProviderModel, "synced-model")
        assert model is not None
        assert model.model_name == "synced-model"
    await runtime.http_client.aclose()
    runtime.engine.dispose()


def test_models_tab_offers_provider_sync_validation_action(
    diagnostics_client: TestClient,
) -> None:
    tab = diagnostics_client.get("/settings/tab/models")

    assert "Fetch and prune models" in tab.text
    assert "/settings/providers/qwen-local/sync-validate-models" in tab.text


def test_provider_sync_validation_prunes_only_model_specific_failures(
    diagnostics_client: TestClient,
) -> None:
    runtime = diagnostics_client.app.state.runtime
    with Session(runtime.engine) as session, session.begin():
        session.add(Provider(id="prune-provider", kind="OPENAI", active=True))
        session.add_all(
            [
                ProviderModel(
                    id="valid-model",
                    provider_id="prune-provider",
                    model_name="valid-model",
                    supports_text=True,
                    active=True,
                ),
                ProviderModel(
                    id="invalid-model",
                    provider_id="prune-provider",
                    model_name="invalid-model",
                    supports_text=True,
                    active=True,
                ),
                ProviderModel(
                    id="retained-model",
                    provider_id="prune-provider",
                    model_name="retained-model",
                    supports_text=True,
                    active=True,
                ),
            ]
        )
        session.add(Route(id="prune-route", task="prune", position=1, active=True))
        session.add(
            RouteCandidate(
                id="invalid-candidate",
                route_id="prune-route",
                model_id="invalid-model",
                position=0,
            )
        )
        session.flush()
        session.add(CandidateHealth(candidate_id="invalid-candidate", failure_count=1))
    runtime.credentials.add("prune-provider", "primary", "secret")

    class PruneAdapter:
        async def sync_models(self, credential: str) -> list[dict[str, object]]:
            assert credential == "secret"
            assert runtime.engine.pool.checkedout() == 0
            return [
                {"id": "valid-model", "name": "valid-model"},
                {"id": "invalid-model", "name": "invalid-model"},
                {"id": "retained-model", "name": "retained-model"},
            ]

        async def complete(self, request, credential: str) -> ModelResponse:
            assert credential == "secret"
            assert runtime.engine.pool.checkedout() == 0
            if request.model == "invalid-model":
                raise ProviderError(
                    ErrorClass.INPUT,
                    "invalid-model is not a valid model ID",
                    status=400,
                    error_type="not_found",
                )
            if request.model == "retained-model":
                raise ProviderError(ErrorClass.AUTH, "credential rejected", status=401)
            return ModelResponse(
                text="OK",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    runtime.provider_router.adapters["prune-provider"] = PruneAdapter()

    response = diagnostics_client.post(
        "/settings/providers/prune-provider/sync-validate-models"
    )

    assert response.status_code == 200
    assert "Fetched 3 model(s); verified 1; deleted 1; retained 1" in response.text
    assert "invalid-model" in response.text
    with Session(runtime.engine) as session:
        valid = session.get(ProviderModel, "valid-model")
        assert valid is not None and valid.verified_at is not None
        assert session.get(ProviderModel, "invalid-model") is None
        assert session.get(RouteCandidate, "invalid-candidate") is None
        assert session.get(CandidateHealth, "invalid-candidate") is None
        assert session.get(ProviderModel, "retained-model") is not None


@pytest.mark.parametrize(
    "error_class",
    [
        ErrorClass.TRANSIENT,
        ErrorClass.RATE_LIMIT,
        ErrorClass.AUTH,
        ErrorClass.INPUT,
    ],
)
def test_provider_sync_validation_retains_only_failed_model_and_continues(
    diagnostics_client: TestClient, error_class: ErrorClass
) -> None:
    runtime = diagnostics_client.app.state.runtime
    with Session(runtime.engine) as session, session.begin():
        session.add(Provider(id="temporary-provider", kind="OPENAI", active=True))
        session.add(
            ProviderModel(
                id="temporary-model",
                provider_id="temporary-provider",
                model_name="temporary-model",
                supports_text=True,
                active=True,
            )
        )
    runtime.credentials.add("temporary-provider", "primary", "secret")

    class TemporaryFailureAdapter:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def sync_models(self, _credential: str) -> list[dict[str, object]]:
            return [{"id": "temporary-model"}, {"id": "succeeding-model"}]

        async def complete(self, request, _credential: str) -> ModelResponse:
            self.calls.append(request.model)
            if request.model == "temporary-model":
                raise ProviderError(error_class, "temporary provider failure")
            return ModelResponse(
                text="OK",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    adapter = TemporaryFailureAdapter()
    runtime.provider_router.adapters["temporary-provider"] = adapter

    response = diagnostics_client.post(
        "/settings/providers/temporary-provider/sync-validate-models"
    )

    assert response.status_code == 200
    assert "verified 1; deleted 0; retained 1" in response.text
    assert adapter.calls == ["temporary-model", "succeeding-model"]
    assert (
        "<code>succeeding-model</code>: temporary provider failure"
        not in response.text
    )
    with Session(runtime.engine) as session:
        assert session.get(ProviderModel, "temporary-model") is not None
        succeeding = session.get(ProviderModel, "succeeding-model")
        assert succeeding is not None and succeeding.verified_at is not None


def test_provider_sync_validation_uses_api_id_instead_of_display_name(
    diagnostics_client: TestClient,
) -> None:
    runtime = diagnostics_client.app.state.runtime
    with Session(runtime.engine) as session, session.begin():
        session.add(Provider(id="openrouter-test", kind="OPENROUTER", active=True))
    runtime.credentials.add("openrouter-test", "primary", "secret")

    class DisplayNameAdapter:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def sync_models(self, _credential: str) -> list[dict[str, object]]:
            return [
                {
                    "id": "qwen/qwen3.7-flash",
                    "name": "Qwen: Qwen3.7 Flash",
                }
            ]

        async def complete(self, request, _credential: str) -> ModelResponse:
            self.calls.append(request.model)
            return ModelResponse(
                text="OK",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    adapter = DisplayNameAdapter()
    runtime.provider_router.adapters["openrouter-test"] = adapter

    response = diagnostics_client.post(
        "/settings/providers/openrouter-test/sync-validate-models"
    )

    assert response.status_code == 200
    assert adapter.calls == ["qwen/qwen3.7-flash"]
    with Session(runtime.engine) as session:
        model = session.get(ProviderModel, "qwen/qwen3.7-flash")
        assert model is not None
        assert model.model_name == "qwen/qwen3.7-flash"
        assert model.verified_at is not None


def test_provider_sync_validation_uses_emulated_openrouter_typed_errors(
    diagnostics_client: TestClient,
) -> None:
    runtime = diagnostics_client.app.state.runtime
    with Session(runtime.engine) as session, session.begin():
        session.add(Provider(id="emulated-openrouter", kind="OPENROUTER", active=True))
        session.add(
            ProviderModel(
                id="filtered-by-privacy",
                provider_id="emulated-openrouter",
                model_name="filtered-by-privacy",
                supports_text=True,
                active=True,
            )
        )
    runtime.credentials.add("emulated-openrouter", "primary", "secret")
    requests: list[tuple[str, str]] = []

    def openrouter(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        assert request.headers["authorization"] == "Bearer secret"
        if request.method == "GET":
            assert request.url.path == "/api/v1/models/user"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "untyped-not-found",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "untyped-bad-request",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "typed-unprocessable",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "authentication-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "rate-limit-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "payment-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "permission-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "timeout-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "network-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "content-policy-failure",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "typed-overloaded",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "embedded-provider-error",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "working-model",
                            "architecture": {"output_modalities": ["text"]},
                        },
                        {
                            "id": "image-only",
                            "architecture": {"output_modalities": ["image"]},
                        },
                    ]
                },
            )
        model = json.loads(request.content)["model"]
        if model == "untyped-not-found":
            return httpx.Response(
                404,
                json={
                    "error": {
                        "code": 404,
                        "message": "arbitrary wording",
                    }
                },
            )
        if model == "untyped-bad-request":
            return httpx.Response(
                400,
                json={
                    "error": {
                        "code": 400,
                        "message": "different arbitrary wording",
                    }
                },
            )
        if model == "typed-unprocessable":
            return httpx.Response(
                422,
                json={
                    "error": {
                        "code": 422,
                        "message": "opaque typed failure",
                        "metadata": {"error_type": "unprocessable"},
                    }
                },
            )
        if model == "authentication-failure":
            return httpx.Response(
                401,
                json={"error": {"code": 401, "message": "opaque auth failure"}},
            )
        if model == "rate-limit-failure":
            return httpx.Response(
                429,
                headers={"Retry-After": "7"},
                json={"error": {"code": 429, "message": "opaque rate failure"}},
            )
        if model == "payment-failure":
            return httpx.Response(
                402,
                json={"error": {"code": 402, "message": "opaque payment failure"}},
            )
        if model == "permission-failure":
            return httpx.Response(
                403,
                json={
                    "error": {"code": 403, "message": "opaque permission failure"}
                },
            )
        if model == "timeout-failure":
            return httpx.Response(
                408,
                json={"error": {"code": 408, "message": "opaque timeout failure"}},
            )
        if model == "network-failure":
            raise httpx.ConnectError("offline", request=request)
        if model == "content-policy-failure":
            return httpx.Response(
                400,
                json={
                    "error": {
                        "code": 400,
                        "message": "opaque policy failure",
                        "metadata": {"error_type": "content_policy_violation"},
                    }
                },
            )
        if model == "typed-overloaded":
            return httpx.Response(
                503,
                json={
                    "error": {
                        "code": 503,
                        "message": "capacity",
                        "metadata": {"error_type": "provider_overloaded"},
                    }
                },
            )
        if model == "embedded-provider-error":
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "error",
                            "message": {"role": "assistant", "content": None},
                            "error": {
                                "code": 502,
                                "message": "upstream unavailable",
                                "metadata": {"error_type": "provider_unavailable"},
                            },
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "generation",
                "model": model,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "OK"},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    emulated_client = httpx.AsyncClient(transport=httpx.MockTransport(openrouter))
    runtime.provider_router.adapters["emulated-openrouter"] = OpenRouterAdapter(
        client=emulated_client,
        base_url="https://openrouter.test/api",
    )

    response = diagnostics_client.post(
        "/settings/providers/emulated-openrouter/sync-validate-models"
    )
    asyncio.run(emulated_client.aclose())

    assert response.status_code == 200
    assert "Fetched 13 model(s); verified 1; deleted 4; retained 9" in response.text
    assert requests[0] == ("GET", "/api/v1/models/user")
    assert requests[1:] == [("POST", "/api/v1/chat/completions")] * 13
    with Session(runtime.engine) as session:
        assert session.get(ProviderModel, "filtered-by-privacy") is None
        assert session.get(ProviderModel, "untyped-not-found") is None
        assert session.get(ProviderModel, "untyped-bad-request") is None
        assert session.get(ProviderModel, "typed-unprocessable") is None
        assert session.get(ProviderModel, "authentication-failure") is not None
        assert session.get(ProviderModel, "rate-limit-failure") is not None
        assert session.get(ProviderModel, "payment-failure") is not None
        assert session.get(ProviderModel, "permission-failure") is not None
        assert session.get(ProviderModel, "timeout-failure") is not None
        assert session.get(ProviderModel, "network-failure") is not None
        assert session.get(ProviderModel, "content-policy-failure") is not None
        assert session.get(ProviderModel, "typed-overloaded") is not None
        assert session.get(ProviderModel, "embedded-provider-error") is not None
        working = session.get(ProviderModel, "working-model")
        assert working is not None and working.verified_at is not None
        assert session.get(ProviderModel, "image-only") is None
