# Test exception text intentionally exercises redaction.
# ruff: noqa: TRY003

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.v2.config import V2Config
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.initialize import initialize
from app.v2.logging import LoggingSettings, LoggingSettingsService, V2ServerLogger
from app.v2.main import _log_middleware
from app.v2.models import RuntimeSetting
from app.v2.runtime import V2Runtime


def _events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_settings_persist_and_rebuild_logger(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "v2.db")
    bootstrap_schema(engine)
    logger = V2ServerLogger(tmp_path)
    service = LoggingSettingsService(engine, logger)
    updated = service.update(
        LoggingSettings(
            folder="configured",
            server_level="WARNING",
            agent_level="DEBUG",
            server_max_bytes=2048,
            agent_max_bytes=4096,
            server_backup_count=2,
            agent_backup_count=3,
        )
    )

    assert updated.folder == "configured"
    with Session(engine) as session:
        row = session.get(RuntimeSetting, "logging")
        assert row is not None
        assert row.value_json["server_level"] == "WARNING"
    rebuilt = LoggingSettingsService(engine, V2ServerLogger(tmp_path)).load_and_apply()
    assert rebuilt == updated


def test_failed_reconfigure_preserves_persisted_and_effective_settings(
    tmp_path: Path,
) -> None:
    engine = create_sqlite_engine(tmp_path / "v2.db")
    bootstrap_schema(engine)
    logger = V2ServerLogger(tmp_path)
    service = LoggingSettingsService(engine, logger)
    prior = service.load_and_apply()
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        service.update(LoggingSettings(folder="escape/logs"))

    with Session(engine) as session:
        row = session.get(RuntimeSetting, "logging")
        assert row is not None
        assert LoggingSettings.from_dict(row.value_json) == prior
    assert logger.settings == prior


def test_enable_disable_is_immediate_and_historical_files_remain_readable(
    tmp_path: Path,
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    logger.log_access("GET", "/first", 200, 1.25, "127.0.0.1")
    path = tmp_path / "logs" / "server.jsonl"
    before = path.read_text(encoding="utf-8")

    logger.reconfigure(LoggingSettings(enabled=False, folder="logs"))
    logger.log_access("GET", "/ignored", 200, 2, "127.0.0.1")

    assert path.read_text(encoding="utf-8") == before
    assert logger.health()["enabled"] is False
    assert logger.read_log("server")["total_lines"] == 1


def test_streams_are_separate_valid_jsonl_with_independent_levels(
    tmp_path: Path,
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(
        LoggingSettings(folder="logs", server_level="WARNING", agent_level="DEBUG")
    )
    logger.log_event(
        "server", "INFO", "server.filtered", "test", "filtered server event"
    )
    logger.log_error("ERROR", "test", 500, "/safe", "server failure")
    logger.log_agent(
        "researcher",
        "agent.debug",
        run_id="run-1",
        message="agent detail",
        level="DEBUG",
        data={"step": 1},
    )

    server = _events(tmp_path / "logs" / "server.jsonl")
    agent = _events(tmp_path / "logs" / "agent.jsonl")
    assert len(server) == len(agent) == 1
    assert server[0]["stream"] == "server"
    assert agent[0]["stream"] == "agent"
    assert agent[0]["run_id"] == "run-1"
    assert agent[0]["data"] == {"step": 1}
    for event in (*server, *agent):
        assert event["timestamp"].endswith("+00:00")
        assert event["schema_version"] == "logging.v1"
        assert event["event_id"]


def test_stream_rotation_and_permissions_are_independent(tmp_path: Path) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(
        LoggingSettings(
            folder="secure",
            server_max_bytes=1024,
            agent_max_bytes=8192,
            server_backup_count=2,
            agent_backup_count=1,
        )
    )
    for index in range(20):
        logger.log_settings_action("rotation", {"index": index, "value": "x" * 120})
    logger.log_agent("agent", "single", message="small")

    folder = tmp_path / "secure"
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert (folder / "server.jsonl.1").exists()
    assert not (folder / "agent.jsonl.1").exists()
    for path in folder.iterdir():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_read_log_includes_rotated_files_in_chronological_order(
    tmp_path: Path,
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(
        LoggingSettings(
            folder="logs",
            server_max_bytes=1024,
            server_backup_count=3,
        )
    )
    for index in range(18):
        logger.log_event(
            "server",
            "INFO",
            "rotation.read",
            "test",
            f"event-{index:02d}",
            data={"padding": "x" * 100},
        )

    result = logger.read_log("server", cursor=0, limit=100)
    messages = [json.loads(line)["message"] for line in result["lines"]]
    active_count = len(
        (tmp_path / "logs" / "server.jsonl").read_text(encoding="utf-8").splitlines()
    )

    assert (tmp_path / "logs" / "server.jsonl.1").exists()
    assert len(messages) > active_count
    assert messages == sorted(messages)
    assert messages[-1] == "event-17"


def test_read_log_streams_files_without_loading_entire_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings())
    logger.log_event("server", "INFO", "streamed", "test", "one")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("read_text loads the entire log file")

    monkeypatch.setattr(Path, "read_text", forbidden)
    result = logger.read_log("server", cursor=0, limit=1)

    assert result["total_lines"] == 1
    assert len(result["lines"]) == 1


@pytest.mark.parametrize(
    "folder", ["/absolute", "../escape", "logs/../../escape", "bad\0name"]
)
def test_folder_validation_rejects_unsafe_paths(tmp_path: Path, folder: str) -> None:
    logger = V2ServerLogger(tmp_path)
    with pytest.raises(ValueError):
        logger.reconfigure(LoggingSettings(folder=folder))


def test_folder_validation_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    logger = V2ServerLogger(tmp_path)
    with pytest.raises(ValueError, match="root"):
        logger.reconfigure(LoggingSettings(folder="escape/logs"))


def test_recursive_redaction_patterns_urls_and_event_bounds(tmp_path: Path) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    logger.log_event(
        "server",
        "INFO",
        "security.test",
        "test",
        "Bearer top-secret and https://user:pass@example.test/a?token=query-secret&ok=1",
        data={
            "password": "db-secret",
            "nested": {"api_key": "key-secret"},
            "authorization": "Basic dXNlcjpwYXNz",
            "safe": "z" * 100_000,
        },
    )

    raw = (tmp_path / "logs" / "server.jsonl").read_text(encoding="utf-8")
    event = json.loads(raw)
    assert len(raw.encode()) <= 65_536
    secrets = (
        "top-secret",
        "user:pass",
        "query-secret",
        "db-secret",
        "key-secret",
        "dXNlcjpwYXNz",
    )
    assert not any(secret in raw for secret in secrets)
    assert event["data"]["password"] == "[REDACTED]"
    assert event["data"]["nested"]["api_key"] == "[REDACTED]"


def test_events_are_strict_json_and_bounded_with_unicode_correlations(
    tmp_path: Path,
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    huge = "😀" * 100_000
    logger.log_event(
        "server",
        "INFO",
        "bounds.test",
        "test",
        "api-key=sk-1234567890abcdef",
        data={
            "metric": float("nan"),
            "url": "https://example.test/?client_secret=hidden-value",
        },
        request_id=huge,
        run_id=huge,
        target_id=huge,
        step_id=huge,
        world_id=huge,
        model_id=huge,
        provider_id=huge,
    )

    raw = (tmp_path / "logs" / "server.jsonl").read_text(encoding="utf-8")

    assert len(raw.encode()) <= 65_536
    assert "sk-1234567890abcdef" not in raw
    assert "hidden-value" not in raw
    json.loads(
        raw,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {value}")
        ),
    )


@pytest.mark.parametrize(("path", "status"), [("/ok", 200), ("/missing", 404)])
def test_http_middleware_logs_one_completion_without_request_metadata(
    tmp_path: Path, path: str, status: int
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    app = FastAPI()
    app.middleware("http")(_log_middleware(logger))

    @app.get("/ok")
    def ok() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get(
        f"{path}?secret=query",
        headers={
            "authorization": "Bearer secret",
            "X-Request-ID": "request-test-123",
        },
    )
    assert response.status_code == status
    assert response.headers["X-Request-ID"] == "request-test-123"
    events = _events(tmp_path / "logs" / "server.jsonl")
    assert len(events) == 1
    assert events[0]["event_type"] == "http.request.completed"
    assert events[0]["request_id"] == "request-test-123"
    assert events[0]["data"]["path"] == path
    raw = json.dumps(events[0])
    assert "query" not in raw
    assert "authorization" not in raw


def test_http_middleware_logs_sanitized_unhandled_exception_and_reraises(
    tmp_path: Path,
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    app = FastAPI()
    app.middleware("http")(_log_middleware(logger))

    @app.get("/explode")
    def explode() -> None:
        raise RuntimeError("Bearer exception-secret")

    with pytest.raises(RuntimeError):
        TestClient(app).get(
            "/explode", headers={"X-Request-ID": "request-error-123"}
        )
    events = _events(tmp_path / "logs" / "server.jsonl")
    assert len(events) == 1
    assert events[0]["event_type"] == "http.request.unhandled_exception"
    assert events[0]["request_id"] == "request-error-123"
    assert events[0]["data"]["status"] == 500
    assert events[0]["data"]["exception_class"] == "RuntimeError"
    assert "test_logging.py" in events[0]["data"]["traceback"]
    assert "exception-secret" not in json.dumps(events[0])


def test_http_middleware_correlates_nested_events_and_validation_errors(
    tmp_path: Path,
) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    app = FastAPI()
    app.middleware("http")(_log_middleware(logger))

    @app.get("/nested")
    def nested(value: int) -> dict[str, int]:
        logger.log_event("server", "INFO", "nested.event", "test", "nested")
        return {"value": value}

    client = TestClient(app)
    response = client.get(
        "/nested", params={"value": "invalid"}, headers={"X-Request-ID": "bad id"}
    )

    assert response.status_code == 422
    request_id = response.headers["X-Request-ID"]
    assert request_id != "bad id"
    assert len(request_id) <= 128
    events = _events(tmp_path / "logs" / "server.jsonl")
    assert len(events) == 1
    assert events[0]["level"] == "WARNING"
    assert events[0]["data"]["status"] == 422
    assert events[0]["request_id"] == request_id

    response = client.get(
        "/nested", params={"value": 3}, headers={"X-Request-ID": "nested-123"}
    )
    assert response.headers["X-Request-ID"] == "nested-123"
    nested_events = _events(tmp_path / "logs" / "server.jsonl")[-2:]
    assert {event["request_id"] for event in nested_events} == {"nested-123"}


def test_health_and_close_expose_stream_state(tmp_path: Path) -> None:
    logger = V2ServerLogger(tmp_path)
    logger.reconfigure(LoggingSettings(folder="logs"))
    assert logger.health() == {
        "enabled": True,
        "folder": str((tmp_path / "logs").resolve()),
        "streams": {"server": True, "agent": True},
        "last_error": None,
    }
    logger.close()
    assert logger.health()["streams"] == {"server": False, "agent": False}


def test_config_reads_logging_root_without_creating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "not-created"
    monkeypatch.setenv("OMNIVERSE_V2_LOG_ROOT", str(root))
    config = V2Config.from_env()
    assert config.logging_root == root
    assert not root.exists()


@pytest.mark.asyncio
async def test_runtime_owns_logging_lifecycle_update_and_shutdown(
    tmp_path: Path,
) -> None:
    seed = tmp_path / "seed.json"
    seed.write_text(
        '[{"id":"w","name":"World","franchise":"F","category":"SF",'
        '"continuity":null,"era":null,"parent":null,"aliases":[],"tags":[]}]',
        encoding="utf-8",
    )
    config = V2Config(
        database_path=tmp_path / "v2.db",
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "credentials.json",
        seed_path=seed,
        browser_enabled=False,
        logging_root=tmp_path / "log-root",
    )
    initialize(config)
    runtime = V2Runtime.build(config)

    await runtime.startup(start_worker=False)
    assert runtime.logging_settings.settings.enabled is True
    runtime.update_logging_settings({"folder": "changed", "agent_level": "DEBUG"})
    assert runtime.server_logger.health()["folder"].endswith("/changed")
    runtime.server_logger.log_agent("test", "agent.test", level="DEBUG")
    await runtime.shutdown()

    server_events = _events(tmp_path / "log-root" / "changed" / "server.jsonl")
    assert [event["event_type"] for event in server_events][-2:] == [
        "server.stopping",
        "server.stopped",
    ]
    assert _events(tmp_path / "log-root" / "changed" / "agent.jsonl")
    assert runtime.server_logger.health()["streams"] == {
        "server": False,
        "agent": False,
    }
