# Injected adapters intentionally ignore request data in routing-only tests.
# ruff: noqa: ARG002

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.credentials import CredentialService, JsonCredentialStore, redact
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.models import (
    CandidateHealth,
    CredentialHealth,
    Provider,
    ProviderModel,
    Route,
    RouteCandidate,
)
from app.v2.providers import (
    AdapterKind,
    ErrorClass,
    GeminiAdapter,
    GenericOpenAIAdapter,
    ModelRequest,
    ModelResponse,
    OpenAIAdapter,
    ProviderError,
    Usage,
)
from app.v2.routing import ProviderRouter, RoutingRequirements


@pytest.mark.parametrize(
    ("adapter_factory", "payload", "expected_text", "expected_tool"),
    [
        (
            GeminiAdapter,
            {
                "candidates": [{"content": {"parts": [{"text": "gemini"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 3,
                    "candidatesTokenCount": 2,
                },
            },
            "gemini",
            None,
        ),
        (
            OpenAIAdapter,
            {
                "choices": [{"message": {"content": "openai"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
            "openai",
            None,
        ),
        (
            GenericOpenAIAdapter,
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "tc1",
                                    "function": {
                                        "name": "lookup",
                                        "arguments": '{"id":"e1"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
            "",
            "lookup",
        ),
    ],
)
@pytest.mark.asyncio
async def test_three_adapter_paths_normalize_response(
    adapter_factory: type,
    payload: dict[str, object],
    expected_text: str,
    expected_tool: str | None,
) -> None:
    async def call(_request: dict[str, object], _secret: str) -> dict[str, object]:
        return payload

    result = await adapter_factory(call).complete(
        ModelRequest(model="m", messages=({"role": "user", "content": "hi"},)),
        "secret",
    )
    assert result.text == expected_text
    assert result.usage.total_tokens > 0
    assert (result.tool_calls[0].name if result.tool_calls else None) == expected_tool


@pytest.mark.integration
def test_credential_store_permissions_redaction_and_write_only_output(
    isolated_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonCredentialStore(isolated_paths["credentials"])
    service = CredentialService(store)
    output = service.add("openai", "primary", "sk-real-secret", weight=2)
    assert output.mask == "********"
    assert "secret" not in output.model_dump()
    assert "sk-real-secret" not in output.model_dump_json()
    assert isolated_paths["credentials"].parent.stat().st_mode & 0o777 == 0o700
    assert isolated_paths["credentials"].stat().st_mode & 0o777 == 0o600
    assert store.resolve(output.opaque_ref) == "sk-real-secret"
    assert redact({"authorization": "Bearer sk-real-secret", "x": "ok"}) == {
        "authorization": "********",
        "x": "ok",
    }
    monkeypatch.setenv("V2_PROVIDER_KEY", "env-secret")
    assert store.resolve("env:V2_PROVIDER_KEY") == "env-secret"
    service.delete(output.credential_id)
    with pytest.raises(KeyError):
        store.resolve(output.opaque_ref)


def test_credential_store_serializes_concurrent_read_modify_write(
    isolated_paths: dict[str, Path],
) -> None:
    class SlowStore(JsonCredentialStore):
        def _read(self):
            values = super()._read()
            time.sleep(0.02)
            return values

    store = SlowStore(isolated_paths["credentials"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(store.put, ("first", "second")))
    assert {store.resolve(ref) for ref in refs} == {"first", "second"}


def test_credential_add_removes_secret_when_metadata_persistence_fails(
    isolated_paths: dict[str, Path],
) -> None:
    class DatabaseUnavailableError(RuntimeError):
        pass

    class FailingService(CredentialService):
        def persist(self, metadata, session=None):
            raise DatabaseUnavailableError

    store = JsonCredentialStore(isolated_paths["credentials"])
    service = FailingService(store, engine=object())
    with pytest.raises(DatabaseUnavailableError):
        service.add("openai", "primary", "must-not-remain")
    assert store._read() == {}


class FakeAdapter:
    kind = AdapterKind.OPENAI

    def __init__(self, outcomes: dict[str, object]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def complete(self, request: ModelRequest, credential: str):
        self.calls.append(credential)
        outcome = self.outcomes[credential]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
@pytest.mark.integration
async def test_provider_candidate_expands_models_at_call_time_and_inherits_default(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    credentials.add("p", "one", "key")
    with Session(engine) as session, session.begin():
        session.add(Provider(id="p", kind="OPENAI", base_url=None, active=True))
        session.add(
            ProviderModel(
                id="later-model",
                provider_id="p",
                model_name="later-model",
                context_window=50_000,
                output_limit=2_000,
                supports_text=True,
                active=True,
            )
        )
        session.add(Route(id="route:DEFAULT", task="DEFAULT", position=0, active=True))
        session.add(
            RouteCandidate(
                id="provider-slot",
                route_id="route:DEFAULT",
                provider_id="p",
                model_id=None,
                position=0,
            )
        )

    class RecordingAdapter:
        kind = AdapterKind.OPENAI

        def __init__(self) -> None:
            self.models: list[str] = []

        async def complete(self, request: ModelRequest, _credential: str):
            self.models.append(request.model)
            return ModelResponse(
                text="ok",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    adapter = RecordingAdapter()
    router = ProviderRouter(engine, credentials, {"p": adapter})

    await router.complete(
        "research.plan", ModelRequest(model="", messages=()), RoutingRequirements()
    )

    assert adapter.models == ["later-model"]


def seed_route(engine, credential_service: CredentialService) -> tuple[str, str]:
    c1 = credential_service.add("p", "one", "key-one")
    c2 = credential_service.add("p", "two", "key-two")
    with Session(engine) as session, session.begin():
        session.add(Provider(id="p", kind="OPENAI", base_url=None, active=True))
        session.add(
            ProviderModel(
                id="pm",
                provider_id="p",
                model_name="model",
                context_window=100_000,
                output_limit=8_000,
                supports_tools=True,
                supports_structured=True,
                supports_text=True,
                active=True,
                verified_at=datetime.now(timezone.utc),
            )
        )
        session.add(Route(id="r", task="research", position=0, active=True))
        session.add(RouteCandidate(id="rc", route_id="r", model_id="pm", position=0))
    return c1.credential_id, c2.credential_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_router_auth_isolates_key_and_rate_limit_cooldown_survives_instance(
    isolated_paths: dict[str, Path],
) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    first_id, second_id = seed_route(engine, credentials)
    adapter = FakeAdapter(
        {
            "key-one": ProviderError(ErrorClass.AUTH, "bad key"),
            "key-two": ProviderError(
                ErrorClass.RATE_LIMIT, "slow down", retry_after=60
            ),
        }
    )
    router = ProviderRouter(engine, credentials, {"p": adapter}, clock=lambda: now)
    with pytest.raises(ProviderError) as caught:
        await router.complete(
            "research", ModelRequest(model="", messages=()), RoutingRequirements()
        )
    assert caught.value.error_class is ErrorClass.RATE_LIMIT
    with Session(engine) as session:
        first = router.credential_health(session, first_id)
        second = router.credential_health(session, second_id)
        assert first.disabled is True
        assert second.cooldown_until == now + timedelta(seconds=60)

    fresh = ProviderRouter(engine, credentials, {"p": adapter}, clock=lambda: now)
    with pytest.raises(ProviderError, match="no healthy route"):
        await fresh.complete(
            "research", ModelRequest(model="", messages=()), RoutingRequirements()
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_router_filters_capabilities_and_does_not_fallback_on_input(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    credentials.add("p", "one", "key")
    with Session(engine) as session, session.begin():
        session.add(Provider(id="p", kind="OPENAI", base_url=None, active=True))
        session.add_all(
            [
                ProviderModel(
                    id="plain",
                    provider_id="p",
                    model_name="plain",
                    context_window=50_000,
                    output_limit=2_000,
                    supports_tools=False,
                    supports_structured=False,
                    supports_text=True,
                    active=True,
                ),
                ProviderModel(
                    id="tools",
                    provider_id="p",
                    model_name="tools",
                    context_window=50_000,
                    output_limit=2_000,
                    supports_tools=True,
                    supports_structured=True,
                    supports_text=True,
                    active=True,
                ),
            ]
        )
        session.add(Route(id="r", task="task", position=0, active=True))
        session.add_all(
            [
                RouteCandidate(
                    id="c1", route_id="r", model_id="plain", position=0
                ),
                RouteCandidate(
                    id="c2", route_id="r", model_id="tools", position=1
                ),
            ]
        )
    adapter = FakeAdapter({"key": ProviderError(ErrorClass.INPUT, "invalid")})
    router = ProviderRouter(engine, credentials, {"p": adapter})
    with pytest.raises(ProviderError) as caught:
        await router.complete(
            "task", ModelRequest(model="", messages=()), RoutingRequirements(tools=True)
        )
    assert caught.value.error_class is ErrorClass.INPUT
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_router_falls_back_after_capability_failure_without_health_penalty(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    credentials.add("first", "primary", "first-key")
    credentials.add("second", "primary", "second-key")
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                Provider(id="first", kind="GEMINI", active=True),
                Provider(id="second", kind="OPENAI", active=True),
                ProviderModel(
                    id="first-model",
                    provider_id="first",
                    model_name="first-model",
                    context_window=50_000,
                    output_limit=2_000,
                    supports_structured=True,
                    active=True,
                ),
                ProviderModel(
                    id="second-model",
                    provider_id="second",
                    model_name="second-model",
                    context_window=50_000,
                    output_limit=2_000,
                    supports_structured=True,
                    active=True,
                ),
                Route(id="capability-route", task="plan", position=0, active=True),
                RouteCandidate(
                    id="first-candidate",
                    route_id="capability-route",
                    model_id="first-model",
                    position=0,
                ),
                RouteCandidate(
                    id="second-candidate",
                    route_id="capability-route",
                    model_id="second-model",
                    position=1,
                ),
            ]
        )
    ok = ModelResponse(
        text="ok",
        tool_calls=(),
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    first = FakeAdapter(
        {"first-key": ProviderError(ErrorClass.CAPABILITY, "schema unsupported")}
    )
    second = FakeAdapter({"second-key": ok})
    router = ProviderRouter(
        engine,
        credentials,
        {"first": first, "second": second},
    )

    response = await router.complete(
        "plan",
        ModelRequest(model="", messages=()),
        RoutingRequirements(structured=True),
    )

    assert response.text == "ok"
    assert first.calls == ["first-key"]
    assert second.calls == ["second-key"]
    with Session(engine) as session:
        assert session.get(CandidateHealth, "first-candidate") is None
        health = session.scalars(select(CredentialHealth)).all()
        assert all(row.failure_count == 0 for row in health)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equal_credentials_round_robin_and_transient_candidate_health(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    seed_route(engine, credentials)
    ok = ModelResponse(
        text="ok",
        tool_calls=(),
        usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    adapter = FakeAdapter({"key-one": ok, "key-two": ok})
    router = ProviderRouter(engine, credentials, {"p": adapter})
    request = ModelRequest(model="", messages=())
    await router.complete("research", request, RoutingRequirements())
    await router.complete("research", request, RoutingRequirements())
    assert set(adapter.calls) == {"key-one", "key-two"}

    adapter.outcomes = {
        "key-one": ProviderError(ErrorClass.TRANSIENT, "down"),
        "key-two": ProviderError(ErrorClass.TRANSIENT, "down"),
    }
    with pytest.raises(ProviderError):
        await router.complete("research", request, RoutingRequirements())
    with Session(engine) as session:
        assert session.get(CandidateHealth, "rc").cooldown_until is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_capability_error_does_not_poison_credential_health(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    seed_route(engine, credentials)
    adapter = FakeAdapter(
        {
            "key-one": ProviderError(ErrorClass.CAPABILITY, "unsupported"),
            "key-two": ProviderError(ErrorClass.CAPABILITY, "unsupported"),
        }
    )
    router = ProviderRouter(engine, credentials, {"p": adapter})
    with pytest.raises(ProviderError):
        await router.complete(
            "research", ModelRequest(model="", messages=()), RoutingRequirements()
        )
    with Session(engine) as session:
        health_rows = session.scalars(select(CredentialHealth)).all()
        assert all(health.failure_count == 0 for health in health_rows)
        assert all(health.last_error_class is None for health in health_rows)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_slow_provider_does_not_hold_sqlite_write_transaction(
    isolated_paths,
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"], busy_timeout_ms=100)
    bootstrap_schema(engine)
    credentials = CredentialService(JsonCredentialStore(isolated_paths["credentials"]))
    seed_route(engine, credentials)
    entered = asyncio.Event()
    release = asyncio.Event()

    class SlowAdapter:
        kind = AdapterKind.OPENAI

        async def complete(self, request, credential):
            entered.set()
            await release.wait()
            return ModelResponse(
                text="ok",
                tool_calls=(),
                usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
            )

    router = ProviderRouter(engine, credentials, {"p": SlowAdapter()})
    pending = asyncio.create_task(
        router.complete(
            "research", ModelRequest(model="", messages=()), RoutingRequirements()
        )
    )
    await entered.wait()

    def write_during_call() -> None:
        with Session(engine) as session, session.begin():
            session.add(Provider(id="concurrent", kind="OPENAI", active=False))

    await asyncio.wait_for(asyncio.to_thread(write_during_call), timeout=0.5)
    release.set()
    assert (await pending).text == "ok"


@pytest.mark.asyncio
async def test_adapter_model_sync_and_filtering() -> None:
    from unittest.mock import AsyncMock

    import httpx

    client = httpx.AsyncClient()
    try:
        openai_adapter = OpenAIAdapter(client=client)

        class MockResponse:
            status_code = 200

            def json(self):
                return {
                    "data": [
                        {"id": "gpt-4o", "name": "GPT-4o"},
                        {"id": "text-embedding-3-small", "name": "Embedding"},
                        {"id": "whisper-1", "name": "Whisper"},
                        {"id": "dall-e-3", "name": "DALL-E"},
                        {"id": "omni-moderation-latest", "name": "Moderation"},
                    ]
                }

        client.get = AsyncMock(return_value=MockResponse())
        models = await openai_adapter.sync_models("sk-test")
        model_ids = [m["id"] for m in models]
        assert model_ids == ["gpt-4o"]

        gemini_adapter = GeminiAdapter(client=client)

        class MockGeminiResponse:
            status_code = 200

            def json(self):
                return {
                    "models": [
                        {
                            "name": "models/gemini-pro",
                            "displayName": "Gemini Pro",
                        },
                        {
                            "name": "models/embedding-001",
                            "displayName": "Embedding",
                        },
                        {
                            "name": "models/imagen-3.0",
                            "displayName": "Imagen",
                        },
                    ]
                }

        client.get = AsyncMock(return_value=MockGeminiResponse())
        gemini_models = await gemini_adapter.sync_models("gem-key")
        client.get.assert_called_once()
        _, kwargs = client.get.call_args
        assert kwargs.get("params") == {"key": "gem-key"}
        gemini_ids = [m["id"] for m in gemini_models]
        assert gemini_ids == ["gemini-pro"]
    finally:
        await client.aclose()
