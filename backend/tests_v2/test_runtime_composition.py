from __future__ import annotations

import asyncio
import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.v2.config import V2Config
from app.v2.contracts import CreateResearchRun, ResearchRunTargetInput
from app.v2.db import SchemaValidationError
from app.v2.domain import RunStatus, StepKind
from app.v2.initialize import initialize
from app.v2.models import (
    ContextManifest,
    CredentialRef,
    OutboxEvent,
    Provider,
    Run,
    SeedRun,
    ToolEvent,
    World,
)
from app.v2.research_runs import ResearchRunKernel
from app.v2.runtime import V2Runtime
from app.v2.worker import ResearchWorker


def _seed(path: Path) -> Path:
    path.write_text(
        '[{"id":"w","name":"World","franchise":"F","category":"SF",'
        '"continuity":null,"era":null,"parent":null,"aliases":[],"tags":[]}]',
        encoding="utf-8",
    )
    return path


def test_config_from_environment_has_no_import_time_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "missing" / "v2.db"
    monkeypatch.setenv("OMNIVERSE_V2_DATABASE_PATH", str(database))
    monkeypatch.setenv("OMNIVERSE_V2_WORKER_CONCURRENCY", "3")
    importlib.reload(importlib.import_module("app.v2.config"))
    assert not database.parent.exists()
    config = V2Config.from_env()
    assert config.database_path == database
    assert config.worker_concurrency == 3
    assert config.require_loopback is True


def test_config_anchors_relative_runtime_paths_to_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OMNIVERSE_V2_DATABASE_PATH", "./data/custom.db")
    monkeypatch.setenv("OMNIVERSE_V2_BLOB_PATH", "relative-blobs")
    config = V2Config.from_env()
    backend = Path(__file__).resolve().parents[1]
    assert config.database_path == backend / "data/custom.db"
    assert config.blob_path == backend / "relative-blobs"


def test_runtime_exposes_explicit_adapter_capabilities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OMNIVERSE_V2_BROWSER_ENABLED", "false")
    config = V2Config(
        database_path=tmp_path / "v2.db",
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "credentials.json",
        seed_path=_seed(tmp_path / "seed.json"),
        browser_enabled=False,
        max_body_bytes=1234,
    )
    runtime = V2Runtime.build(config)
    assert runtime.adapter_status["browser"] == {
        "available": False,
        "detail": "disabled by configuration",
    }
    assert runtime.adapter_status["pdf"]["available"] is True
    assert "available" in runtime.adapter_status["ocr"]
    assert runtime.workflow.acquisition_policy.max_body_bytes == 1234


@pytest.mark.integration
def test_explicit_initialize_is_idempotent_and_seeds_only_worlds_and_policies(
    tmp_path: Path,
) -> None:
    config = V2Config(
        database_path=tmp_path / "data" / "v2.db",
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "secrets" / "credentials.json",
        seed_path=_seed(tmp_path / "seed.json"),
    )
    first = initialize(config)
    second = initialize(config)
    assert first.imported_count == 1
    assert second.imported_count == 0
    assert config.blob_path.is_dir()
    with Session(V2Runtime.engine_for(config)) as session:
        assert session.scalar(select(func.count()).select_from(World)) == 1
        assert session.scalar(select(func.count()).select_from(SeedRun)) == 1
        assert session.scalar(select(func.count()).select_from(Provider)) == 0
        assert session.scalar(select(func.count()).select_from(CredentialRef)) == 0
        assert session.scalar(select(func.count()).select_from(Run)) == 0


def test_initialize_refuses_unrecognized_nonempty_database(tmp_path: Path) -> None:
    database = tmp_path / "not-ours.db"
    database.write_bytes(b"not sqlite")
    config = V2Config(
        database_path=database,
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "credentials.json",
        seed_path=_seed(tmp_path / "seed.json"),
    )
    with pytest.raises(SchemaValidationError):
        initialize(config)


@pytest.mark.asyncio
async def test_runtime_startup_requires_initialized_schema(tmp_path: Path) -> None:
    config = V2Config(
        database_path=tmp_path / "missing.db",
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "credentials.json",
        seed_path=_seed(tmp_path / "seed.json"),
    )
    runtime = V2Runtime.build(config)
    with pytest.raises(SchemaValidationError):
        await runtime.startup(start_worker=False)
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_runtime_startup_requires_the_configured_seed_hash(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path / "seed.json")
    config = V2Config(
        database_path=tmp_path / "v2.db",
        blob_path=tmp_path / "blobs",
        credentials_path=tmp_path / "credentials.json",
        seed_path=seed,
    )
    initialize(config)
    seed.write_text("[]", encoding="utf-8")
    runtime = V2Runtime.build(config)
    with pytest.raises(SchemaValidationError, match="configured world seed"):
        await runtime.startup(start_worker=False)
    await runtime.shutdown()


class _Kernel:
    def __init__(self, values: list[object | None]) -> None:
        self.values = values
        self.reconciled = 0

    def reconcile_startup(self, _now) -> int:
        self.reconciled += 1
        return 0


class _Workflow:
    def __init__(self, values: list[bool | Exception]) -> None:
        self.values = values
        self.calls: list[str] = []

    async def run_next(self, run_id: str) -> bool:
        self.calls.append(run_id)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.asyncio
async def test_worker_is_fair_continues_failures_and_stops_cleanly() -> None:
    run_ids = iter(["a", "b", "c", None])
    workflow = _Workflow([True, RuntimeError("durable failure"), True])
    worker = ResearchWorker(
        _Kernel([]), workflow, next_run=lambda: next(run_ids), poll_seconds=0
    )
    assert await worker.run_until_idle() == 2
    assert workflow.calls == ["a", "b", "c"]
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0)
    await worker.stop()
    await task


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_multi_run_worker_failure_matrix_is_durable_and_non_blocking(
    isolated_paths,
) -> None:
    from app.v2.db import bootstrap_schema, create_sqlite_engine

    now = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    scenarios = (
        "auth-fallback",
        "rate-limit",
        "search-blocked",
        "browser-unavailable",
        "pdf-ocr-required",
        "ocr-unavailable",
        "malformed-output",
        "context-overflow",
        "healthy",
    )
    with Session(engine) as session, session.begin():
        session.add_all(
            World(id=name, name=name, franchise="F", category="SF")
            for name in scenarios
        )
    kernel = ResearchRunKernel(engine)
    run_scenarios = {}
    for scenario in scenarios:
        run = kernel.create(
            CreateResearchRun(
                objective=scenario,
                scope={"continuity": "prime"},
                targets=(
                    ResearchRunTargetInput(world_id=scenario, objective=scenario),
                ),
                max_attempts=2,
            ),
            f"matrix-{scenario}",
        )
        run_scenarios[run.id] = scenario

    failure_steps = {
        "rate-limit": StepKind.PLAN,
        "search-blocked": StepKind.SCOUT,
        "browser-unavailable": StepKind.ACQUIRE,
        "pdf-ocr-required": StepKind.ACQUIRE,
        "ocr-unavailable": StepKind.ACQUIRE,
        "malformed-output": StepKind.PLAN,
        "context-overflow": StepKind.PLAN,
    }
    error_classes = {
        "search-blocked": "SEARCH_BLOCKED",
        "browser-unavailable": "BROWSER_UNAVAILABLE",
        "pdf-ocr-required": "OCR_REQUIRED",
        "ocr-unavailable": "OCR_UNAVAILABLE",
        "malformed-output": "MALFORMED_STRUCTURED_OUTPUT",
        "context-overflow": "CONTEXT_OVERFLOW",
    }

    class MatrixWorkflow:
        async def run_next(self, run_id: str) -> bool:
            scenario = run_scenarios[run_id]
            lease = kernel.lease_next(
                "matrix-worker", now, timedelta(minutes=5), run_id=run_id
            )
            if lease is None:
                return False
            if scenario == "auth-fallback" and lease.kind is StepKind.PLAN:
                with Session(engine) as session, session.begin():
                    session.add(
                        ToolEvent(
                            id="tool-auth-fallback",
                            step_id=lease.step_id,
                            status="FAILED",
                            input_json={"credential_id": "key-primary"},
                            error_class="AUTH",
                            idempotency_key="matrix-auth-fallback",
                        )
                    )
            if failure_steps.get(scenario) is lease.kind:
                if scenario in error_classes:
                    with Session(engine) as session, session.begin():
                        session.add(
                            ToolEvent(
                                id=f"tool-{scenario}",
                                step_id=lease.step_id,
                                status="FAILED",
                                input_json={"scenario": scenario},
                                error_class=error_classes[scenario],
                                idempotency_key=f"matrix-{scenario}",
                            )
                        )
                retryable = scenario == "rate-limit"
                kernel.checkpoint_failure(
                    lease,
                    f"{scenario}: inspectable failure",
                    retryable=retryable,
                    retry_at=now + timedelta(minutes=1) if retryable else None,
                    now=now,
                )
                return True
            kernel.checkpoint_success(
                lease,
                effect_key=f"matrix:{lease.step_id}",
                output_refs=(),
                state={
                    "outcome": "COMPLETE",
                    "fallback": scenario == "auth-fallback",
                },
                now=now,
            )
            return True

    schedule = iter([*run_scenarios] * (len(StepKind) + 1) + [None])
    worker = ResearchWorker(
        kernel,
        MatrixWorkflow(),
        next_run=lambda: next(schedule),
        poll_seconds=0,
    )
    assert await worker.run_until_idle() > 0

    projections = {
        scenario: kernel.get(run_id) for run_id, scenario in run_scenarios.items()
    }
    assert projections["healthy"].outcome.value == "COMPLETE"
    assert projections["auth-fallback"].outcome.value == "COMPLETE"
    assert projections["rate-limit"].status is RunStatus.WAITING_RETRY
    assert next(
        step
        for step in projections["rate-limit"].steps
        if step.status is RunStatus.WAITING_RETRY
    ).retry_due_at == now + timedelta(minutes=1)
    for scenario in failure_steps.keys() - {"rate-limit"}:
        assert projections[scenario].status is RunStatus.FAILED
        assert "inspectable failure" in next(
            step.error for step in projections[scenario].steps if step.error
        )

    with Session(engine) as session:
        tool_events = session.scalars(select(ToolEvent)).all()
        outbox = session.scalars(select(OutboxEvent)).all()
        manifests = session.scalars(select(ContextManifest)).all()
    assert {event.error_class for event in tool_events} >= {
        "AUTH",
        *error_classes.values(),
    }
    persisted = json.dumps(
        [event.payload_json for event in outbox]
        + [event.input_json for event in tool_events]
        + [manifest.manifest_json for manifest in manifests],
        sort_keys=True,
    ).lower()
    assert "secret" not in persisted
    assert "raw_body" not in persisted
    assert "transcript" not in persisted
