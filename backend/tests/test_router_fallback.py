import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session, select

from app.core.router import calculate_candidate_hash, router
from app.db.operational_session import init_operational_db, operational_engine
from app.db.schema import (
    AgentRouteFallback,
    CandidateHealth,
    ProviderConfig,
    ProviderKey,
)
from app.db.settings_session import init_settings_db, settings_engine

init_settings_db()

TEST_DIR = Path(__file__).parent


def _find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _seed_provider(
    base_url: str,
    api_keys: list[str],
    models: str = "gpt-4",
    provider_type: str = "custom",
) -> ProviderConfig:
    """Create provider + keys + route in test DB, return provider."""
    with Session(settings_engine) as session:
        p = ProviderConfig(
            name="test-provider",
            provider_type=provider_type,
            base_url=base_url,
            models=models,
        )
        session.add(p)
        session.flush()

        for i, key in enumerate(api_keys):
            session.add(ProviderKey(provider_id=p.id, api_key=key, priority=i))

        session.add(
            AgentRouteFallback(
                task_type="TEST", provider_id=p.id, models=models, priority=0
            )
        )

        session.commit()
        session.refresh(p)
        return p


def _set_bad_keys(base_url: str, keys: list[str]):
    with httpx.Client() as client:
        r = client.post(f"{base_url}/__control__/bad_keys", json={"keys": keys})
        assert r.status_code == 200, f"bad_keys control failed: {r.text}"


@pytest.fixture(scope="module")
def fake_llm_server():
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "fake_llm_server:app",
            "--app-dir",
            str(TEST_DIR),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        env=os.environ,
    )

    for _ in range(30):
        try:
            with httpx.Client() as client:
                r = client.get(f"{base_url}/health", timeout=1)
                if r.status_code == 200:
                    break
        except (httpx.ConnectError, httpx.ReadTimeout):
            time.sleep(0.3)
    else:
        proc.kill()
        proc.wait(timeout=5)
        raise RuntimeError(
            "Fake LLM server did not start"
        )

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


@pytest.fixture(autouse=True)
def cleanup_settings():
    init_settings_db()
    init_operational_db()
    with Session(settings_engine) as session:
        session.query(ProviderConfig).delete()
        session.query(ProviderKey).delete()
        session.query(AgentRouteFallback).delete()
        session.commit()
    with Session(operational_engine) as session:
        session.query(CandidateHealth).delete()
        session.commit()
    return


# ── Key fallback tests ──────────────────────────────────────────────


class TestKeyFallback:
    @pytest.mark.asyncio
    async def test_bad_key_falls_to_good_key(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["bad-key"])
        _seed_provider(base_url, api_keys=["bad-key", "good-key"])

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        assert "good-key" in content

    @pytest.mark.asyncio
    async def test_all_keys_exhausted(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["bad-1", "bad-2"])
        _seed_provider(base_url, api_keys=["bad-1", "bad-2"])

        with pytest.raises(RuntimeError, match="All fallback options exhausted"):
            await router.run_model(
                "TEST",
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_single_key_success(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, [])
        _seed_provider(base_url, api_keys=["only-key"])

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        assert "only-key" in content

    @pytest.mark.asyncio
    async def test_key_priority_order(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["lowest", "middle"])

        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="priority-provider",
                provider_type="custom",
                base_url=base_url,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            for key, prio in [("lowest", 2), ("middle", 0), ("highest", 1)]:
                session.add(ProviderKey(provider_id=p.id, api_key=key, priority=prio))

            session.add(
                AgentRouteFallback(
                    task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
                )
            )
            session.commit()

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        assert "highest" in content

    @pytest.mark.asyncio
    async def test_no_keys_available(self, fake_llm_server):
        base_url = fake_llm_server

        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="no-keys-provider",
                provider_type="openai",
                base_url=base_url,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            session.add(
                AgentRouteFallback(
                    task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
                )
            )
            session.commit()

        with pytest.raises(RuntimeError, match="All fallback options exhausted"):
            await router.run_model(
                "TEST",
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_no_routes_for_task(self, _fake_llm_server):
        with pytest.raises(
            ValueError, match="No routing configured for task 'NONEXISTENT'"
        ):
            await router.run_model(
                "NONEXISTENT",
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_provider_without_provider_type_skipped(self, _fake_llm_server):
        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="no-type-provider",
                provider_type=None,
                base_url=None,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            session.add(
                AgentRouteFallback(
                    task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
                )
            )
            session.commit()

        with pytest.raises(RuntimeError, match="All fallback options exhausted"):
            await router.run_model(
                "TEST",
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_keys_models_cartesian_order(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["key1"])

        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="cartesian-provider",
                provider_type="custom",
                base_url=base_url,
                models="gpt-4, gpt-3.5",
            )
            session.add(p)
            session.flush()

            for i, key in enumerate(["key1", "key2"]):
                session.add(ProviderKey(provider_id=p.id, api_key=key, priority=i))

            session.add(
                AgentRouteFallback(
                    task_type="TEST",
                    provider_id=p.id,
                    models="gpt-4,gpt-3.5",
                    priority=0,
                )
            )
            session.commit()

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        # key1 fails on both models, then key2 succeeds on model1
        assert "key2" in content

    @pytest.mark.asyncio
    async def test_custom_prefix(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, [])
        _seed_provider(base_url, api_keys=["test-key"], provider_type="custom")

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        assert "test-key" in content

    @pytest.mark.asyncio
    async def test_fallback_to_default_route(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, [])

        # Seed provider and default route
        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="default-route-provider",
                provider_type="custom",
                base_url=base_url,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            session.add(
                ProviderKey(provider_id=p.id, api_key="default-key", priority=0)
            )

            # Setup DEFAULT fallback route
            session.add(
                AgentRouteFallback(
                    task_type="DEFAULT", provider_id=p.id, models="gpt-4", priority=0
                )
            )
            session.commit()

        # Run a task with NO specific routing (e.g. "UNKNOWN_TASK")
        result = await router.run_model(
            "UNKNOWN_TASK",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        assert "default-key" in content

    @pytest.mark.asyncio
    async def test_route_models_none_falls_back_to_provider_models(
        self, fake_llm_server
    ):
        base_url = fake_llm_server
        _set_bad_keys(base_url, [])

        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="none-models-provider",
                provider_type="custom",
                base_url=base_url,
                models="gpt-3.5-turbo",
            )
            session.add(p)
            session.flush()

            session.add(
                ProviderKey(provider_id=p.id, api_key="none-models-key", priority=0)
            )

            # AgentRouteFallback with models=None
            session.add(
                AgentRouteFallback(
                    task_type="TEST_NONE_MODELS",
                    provider_id=p.id,
                    models=None,
                    priority=0,
                )
            )
            session.commit()

        result = await router.run_model(
            "TEST_NONE_MODELS",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result[0].choices[0].message.content
        assert "none-models-" in content
        assert result[1] == "openai/gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_provider_no_keys_custom_type(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, [])

        with Session(settings_engine) as session:
            p = ProviderConfig(
                name="no-keys-custom-provider",
                provider_type="openai",
                base_url=base_url,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            session.add(
                AgentRouteFallback(
                    task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
                )
            )
            session.commit()

        with pytest.raises(RuntimeError, match="All fallback options exhausted"):
            await router.run_model(
                "TEST",
                messages=[{"role": "user", "content": "hi"}],
            )


class TestCandidateHealth:
    @pytest.mark.asyncio
    async def test_circuit_breaker_disables_after_5_failures(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["bad-key"])
        _seed_provider(base_url, api_keys=["bad-key"], models="gpt-4")

        # 5 failures should disable it
        for _ in range(5):
            with pytest.raises(RuntimeError, match="All fallback options exhausted"):
                await router.run_model(
                    "TEST", messages=[{"role": "user", "content": "hi"}]
                )

        # 6th call should still fail, but verify it's disabled in DB
        with Session(operational_engine) as session:
            from app.db.schema import CandidateHealth

            health = session.exec(select(CandidateHealth)).first()

            assert health is not None
            assert health.failure_count == 5
            assert health.disabled_until is not None

    @pytest.mark.asyncio
    async def test_disabled_candidate_skipped(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["bad-key"])
        _seed_provider(base_url, api_keys=["bad-key", "good-key"], models="gpt-4")

        # Force first key to be disabled
        with Session(settings_engine) as s_session:
            # We need the specific key id. Seed provider does this.
            # Let's just find the one for 'bad-key'
            from app.db.schema import ProviderKey

            key = s_session.exec(
                select(ProviderKey).where(ProviderKey.api_key == "bad-key")
            ).first()
            provider = s_session.get(ProviderConfig, key.provider_id)
            c_hash = calculate_candidate_hash(provider.id, key.id, "gpt-4")

        with Session(operational_engine) as o_session:
            from app.db.schema import CandidateHealth
            health = CandidateHealth(
                candidate_hash=c_hash,
                provider_id=provider.id,
                key_id=key.id,
                model="gpt-4",
                failure_count=5,
                disabled_until=datetime.utcnow() + timedelta(hours=1),
            )
            o_session.add(health)
            o_session.commit()


        # Should skip bad-key and go straight to good-key
        result = await router.run_model(
            "TEST", messages=[{"role": "user", "content": "hi"}]
        )
        content = result[0].choices[0].message.content
        assert "good-key" in content

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["bad-key"])
        _seed_provider(base_url, api_keys=["bad-key", "good-key"], models="gpt-4")

        # Fail 3 times with bad-key (by making good-key bad temporarily)
        _set_bad_keys(base_url, ["bad-key", "good-key"])
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await router.run_model(
                    "TEST", messages=[{"role": "user", "content": "hi"}]
                )

        # Now make good-key work
        _set_bad_keys(base_url, ["bad-key"])
        await router.run_model("TEST", messages=[{"role": "user", "content": "hi"}])

        with Session(operational_engine) as session:
            from app.db.schema import CandidateHealth

            health = session.exec(
                select(CandidateHealth).where(CandidateHealth.model == "gpt-4")
            ).all()
            # Check that at least one candidate (the successful one)
            # has failure_count == 0
            assert any(h.failure_count == 0 for h in health)


# (Remove this redundant test function)
