# ruff: noqa: ARG002, I001, TRY003

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from app.v2.acquisition import AcquisitionPolicy, AcquisitionService, HttpResponse
from app.v2.blobs import BlobStore
from app.v2.contracts import StepLease
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.domain import RunStatus, StepKind
from app.v2.gateway import StructuredModelGateway, StructuredOutputError
from app.v2.preprocessing import MiniCPMPreprocessor, PreprocessingStatus
from app.v2.providers import (
    ErrorClass,
    CircuitBreaker,
    GeminiAdapter,
    ModelRequest,
    ModelResponse,
    OpenAIAdapter,
    ProviderError,
    ToolCall,
    Usage,
)
from app.v2.routing import ProviderRouter, RoutingRequirements
from app.v2.search import DuckDuckGoSearch
from app.v2.worker import ResearchWorker
from app.v2.workflow import ResearchWorkflow, SimulatedCrashError


class EventLogger:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[dict[str, object]] = []
        self.fail = fail

    def log_agent(self, component, event_type, **values) -> None:
        if self.fail:
            raise OSError("logger unavailable")
        self.events.append({"component": component, "event_type": event_type, **values})


class Output(BaseModel):
    value: str


def test_circuit_breaker_allow_request_does_not_deadlock() -> None:
    breaker = CircuitBreaker()
    completed = threading.Event()

    def check() -> None:
        breaker.allow_request()
        completed.set()

    threading.Thread(target=check, daemon=True).start()
    assert completed.wait(0.2), "allow_request deadlocked while reading breaker state"


def event(logger: EventLogger, event_type: str) -> dict[str, object]:
    return next(item for item in logger.events if item["event_type"] == event_type)


@pytest.mark.asyncio
async def test_documented_reasoning_and_tool_calls_are_normalized() -> None:
    async def openai_call(_request, _credential):
        return {
            "id": "response-1",
            "model": "model-1",
            "choices": [
                {
                    "message": {
                        "content": "normal text",
                        "reasoning_content": "explicit returned reasoning",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "lookup",
                                    "arguments": '{"token":"secret-value","id":"x"}',
                                },
                            }
                        ],
                    }
                }
            ],
        }

    response = await OpenAIAdapter(openai_call).complete(
        ModelRequest(model="m", messages=()), "credential"
    )
    assert response.returned_reasoning == "explicit returned reasoning"
    assert response.reasoning_field == "message.reasoning_content"
    assert response.tool_calls[0].name == "lookup"

    async def no_reasoning(_request, _credential):
        return {"choices": [{"message": {"content": "plain"}}]}

    absent = await OpenAIAdapter(no_reasoning).complete(
        ModelRequest(model="m", messages=()), "credential"
    )
    assert absent.returned_reasoning is None
    assert absent.reasoning_field is None

    async def gemini_call(_request, _credential):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "thought returned", "thought": True},
                            {"text": "answer"},
                        ]
                    }
                }
            ]
        }

    gemini = await GeminiAdapter(gemini_call).complete(
        ModelRequest(model="m", messages=()), "credential"
    )
    assert gemini.text == "answer"
    assert gemini.returned_reasoning == "thought returned"
    assert gemini.reasoning_field == "candidates.content.parts[thought]"


@pytest.mark.asyncio
async def test_gateway_logs_model_output_reasoning_tools_repair_and_failure(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    logger = EventLogger()

    class Router:
        def __init__(self, responses):
            self.responses = iter(responses)

        async def complete(self, _task, _request, _requirements, **_correlation):
            value = next(self.responses)
            if isinstance(value, Exception):
                raise value
            return value

    malformed = ModelResponse(
        text="not-json",
        tool_calls=(
            ToolCall(id="call-1", name="lookup", arguments={"api_key": "sk-x"}),
        ),
        usage=Usage(input_tokens=3, output_tokens=2, total_tokens=5),
        returned_reasoning="returned thought",
        reasoning_field="message.reasoning_content",
        provider_id="provider-1",
        model_id="model-1",
    )
    valid = malformed.model_copy(
        update={"text": json.dumps({"value": "Bearer secret-token " + "x" * 5000})}
    )
    result = await StructuredModelGateway(
        engine, Router([malformed, valid]), logger=logger
    ).call(
        run_id=None,
        target_id="target-1",
        world_id="world-1",
        attempt_number=2,
        step_kind="PLAN",
        task="task-1",
        role_prompt="prompt/v1: instructions",
        payload={"authorization": "Bearer input-secret"},
        output_type=Output,
        step_id=None,
    )
    assert result.value.endswith("x")
    assert (
        event(logger, "model.reasoning.returned")["data"]["reasoning"]
        == "returned thought"
    )
    assert (
        event(logger, "model.tool_call.returned")["data"]["arguments"]["api_key"]
        == "[REDACTED]"
    )
    logged_output = json.dumps(event(logger, "model.output.validated"))
    assert "secret-token" not in logged_output
    assert len(logged_output) < 10_000
    assert event(logger, "model.repair.succeeded")["target_id"] == "target-1"
    assert event(logger, "model.call.started")["data"]["attempt_number"] == 2
    assert event(logger, "model.call.started")["data"]["step_kind"] == "PLAN"

    no_reasoning_logger = EventLogger()
    plain = ModelResponse(
        text=json.dumps({"value": "plain"}),
        tool_calls=(),
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    await StructuredModelGateway(
        engine, Router([plain]), logger=no_reasoning_logger
    ).call(
        run_id=None,
        task="plain-task",
        role_prompt="prompt/v1",
        payload={},
        output_type=Output,
    )
    assert not any(
        item["event_type"] == "model.reasoning.returned"
        for item in no_reasoning_logger.events
    )

    failed_logger = EventLogger()
    with pytest.raises(ProviderError):
        await StructuredModelGateway(
            engine,
            Router([ProviderError(ErrorClass.TRANSIENT, "Bearer provider-secret")]),
            logger=failed_logger,
        ).call(
            run_id="run-2",
            task="task-2",
            role_prompt="prompt/v1",
            payload={},
            output_type=Output,
        )
    assert event(failed_logger, "model.call.failed")["level"] == "ERROR"
    assert "provider-secret" not in json.dumps(failed_logger.events)

    rejected_logger = EventLogger()
    with pytest.raises(StructuredOutputError):
        await StructuredModelGateway(
            engine,
            Router([malformed, malformed]),
            logger=rejected_logger,
        ).call(
            run_id="run-3",
            task="task-3",
            role_prompt="prompt/v1",
            payload={},
            output_type=Output,
        )
    assert event(rejected_logger, "model.repair.failed")["level"] == "ERROR"


@pytest.mark.asyncio
async def test_router_logs_each_fallback_attempt_and_never_logs_secret(
    isolated_paths: dict[str, Path],
) -> None:
    from app.v2.credentials import CredentialService, JsonCredentialStore
    from app.v2.models import Provider, ProviderModel, Route, RouteCandidate
    from sqlalchemy.orm import Session

    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    credentials.add("p", "first", "secret-one")
    credentials.add("p", "second", "secret-two")
    with Session(engine) as session, session.begin():
        session.add(Provider(id="p", kind="OPENAI", active=True))
        session.add(
            ProviderModel(
                id="pm",
                provider_id="p",
                model_name="m",
                context_window=1000,
                output_limit=100,
                supports_tools=True,
                supports_structured=True,
                supports_text=True,
                active=True,
            )
        )
        session.add(Route(id="r", task="task", position=0, active=True))
        session.add(RouteCandidate(id="rc", route_id="r", model_id="pm", position=0))

    class Adapter:
        def __init__(self):
            self.calls = 0

        async def complete(self, _request, credential):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError(ErrorClass.AUTH, "bad credential")
            return ModelResponse(
                text="ok",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    logger = EventLogger()
    router = ProviderRouter(engine, credentials, {"p": Adapter()}, logger=logger)
    result = await router.complete(
        "task",
        ModelRequest(model="", messages=()),
        RoutingRequirements(),
        run_id="run-1",
    )
    assert result.text == "ok"
    assert [item["event_type"] for item in logger.events].count(
        "provider.attempt.started"
    ) == 2
    assert event(logger, "provider.fallback")["data"]["error_class"] == "AUTH"
    assert "secret-one" not in json.dumps(logger.events)
    assert "secret-two" not in json.dumps(logger.events)


@pytest.mark.asyncio
async def test_workflow_logs_correlated_success_failure_cancellation_and_crash() -> (
    None
):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def lease(kind=StepKind.PLAN):
        return StepLease(
            step_id="step-1",
            run_id="run-1",
            target_id="target-1",
            world_id="world-1",
            kind=kind,
            owner="owner",
            attempt_number=3,
            lease_expires_at=now + timedelta(minutes=1),
        )

    class Kernel:
        def __init__(self):
            self.current = lease()
            self.status = RunStatus.RUNNING

        def get(self, _run_id):
            return SimpleNamespace(outcome=None, status=self.status)

        def lease_next(self, *_args, **_kwargs):
            value, self.current = self.current, None
            return value

        def checkpoint_success(self, *_args, **_kwargs):
            pass

        def checkpoint_failure(self, *_args, **_kwargs):
            pass

        def cancel_at_safe_boundary(self, *_args, **_kwargs):
            pass

    async def run_case(outcome, *, status=RunStatus.RUNNING, crash=False):
        kernel = Kernel()
        kernel.status = status
        logger = EventLogger()
        workflow = ResearchWorkflow(
            None, kernel, object(), object(), object(), logger=logger, clock=lambda: now
        )

        async def execute(_lease):
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        workflow._execute = execute
        if crash:
            workflow.crash_after_effect_for = StepKind.PLAN
        if crash:
            with pytest.raises(SimulatedCrashError):
                await workflow.run_next("run-1")
        else:
            await workflow.run_next("run-1")
        return logger

    succeeded = await run_case({})
    assert event(succeeded, "step.succeeded")["attempt_number"] == 3
    failed = await run_case(ValueError("Bearer workflow-secret"))
    assert event(failed, "step.failed")["world_id"] == "world-1"
    assert "workflow-secret" not in json.dumps(failed.events)
    retrying = await run_case(
        ProviderError(ErrorClass.TRANSIENT, "retry", retry_after=7)
    )
    assert event(retrying, "step.retry_scheduled")["data"]["retry_after_seconds"] == 7
    cancelled = await run_case({}, status=RunStatus.CANCELLING)
    assert event(cancelled, "step.cancelled")["target_id"] == "target-1"
    crashed = await run_case({}, crash=True)
    assert event(crashed, "step.crashed")["level"] == "CRITICAL"


@pytest.mark.asyncio
async def test_worker_logs_unexpected_exception_and_logger_failure_is_nonfatal() -> (
    None
):
    class Workflow:
        async def run_next(self, _run_id):
            raise RuntimeError("Bearer worker-secret")

    logger = EventLogger()
    worker = ResearchWorker(
        object(), Workflow(), next_run=lambda: "run-1", logger=logger
    )
    assert await worker.run_next() is False
    assert event(logger, "worker.crashed")["level"] == "ERROR"
    assert "worker-secret" not in json.dumps(logger.events)

    worker = ResearchWorker(
        object(), Workflow(), next_run=lambda: "run-1", logger=EventLogger(fail=True)
    )
    assert await worker.run_next() is False


@pytest.mark.asyncio
async def test_search_acquisition_and_minicpm_emit_tool_events(tmp_path: Path) -> None:
    logger = EventLogger()
    search_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, content=b'<a class="result__a" href="https://example.test/a">A</a>'
            )
        )
    )
    await DuckDuckGoSearch(search_client, logger=logger).search(
        "Bearer query-secret", limit=1
    )
    assert event(logger, "search.succeeded")["data"]["result_count"] == 1
    assert "query-secret" not in json.dumps(logger.events)
    await search_client.aclose()

    class Resolver:
        async def resolve(self, _host):
            return ("93.184.216.34",)

    class Transport:
        async def get(self, url, **_kwargs):
            return HttpResponse(200, {}, b"source body", "text/plain", url)

    acquisition = AcquisitionService(
        None, BlobStore(tmp_path / "blobs"), Resolver(), Transport(), logger=logger
    )
    await acquisition.fetch_http("https://example.test/a", AcquisitionPolicy())
    assert event(logger, "acquisition.http.succeeded")["data"]["body_length"] == 11
    assert "source body" not in json.dumps(logger.events)

    engine = create_sqlite_engine(tmp_path / "acquisition.db")
    bootstrap_schema(engine)
    persisted = AcquisitionService(
        engine,
        BlobStore(tmp_path / "persisted-blobs"),
        Resolver(),
        Transport(),
        logger=logger,
    )
    await persisted.acquire(
        "https://example.test/a",
        AcquisitionPolicy(),
        idempotency_key="activity-cache",
    )
    assert event(logger, "acquisition.cache.started")
    assert event(logger, "acquisition.cache.succeeded")["data"]["hit"] is False

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(503))
    )
    result = await MiniCPMPreprocessor(client=client, logger=logger).reformat(
        "Captain Nova 20"
    )
    assert result.status is PreprocessingStatus.SERVER_ERROR
    fallback = event(logger, "preprocessor.fallback")
    assert fallback["data"]["status"] == "SERVER_ERROR"
    assert "Captain Nova 20" not in json.dumps(logger.events)
    await client.aclose()
