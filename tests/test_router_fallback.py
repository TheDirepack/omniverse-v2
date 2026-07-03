import os
import sys
import time
import socket
import subprocess
from pathlib import Path

import pytest
import httpx

from sqlmodel import Session

from app.db.schema import ProviderConfig, ProviderKey, AgentRouteFallback
from app.db.session import engine
from app.core.router import router


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
    with Session(engine) as session:
        p = ProviderConfig(
            name="test-provider",
            provider_type=provider_type,
            base_url=base_url,
            models=models,
        )
        session.add(p)
        session.flush()

        for i, key in enumerate(api_keys):
            session.add(ProviderKey(
                provider_id=p.id, api_key=key, priority=i
            ))

        session.add(AgentRouteFallback(
            task_type="TEST", provider_id=p.id, models=models, priority=0
        ))

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
        [sys.executable, "-m", "uvicorn", "fake_llm_server:app",
         "--app-dir", str(TEST_DIR),
         "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "error"],
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
        raise RuntimeError("Fake LLM server did not start")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


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

        content = result["choices"][0]["message"]["content"]
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

        content = result["choices"][0]["message"]["content"]
        assert "only-key" in content

    @pytest.mark.asyncio
    async def test_key_priority_order(self, fake_llm_server):
        base_url = fake_llm_server
        _set_bad_keys(base_url, ["lowest", "middle"])

        with Session(engine) as session:
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

            session.add(AgentRouteFallback(
                task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
            ))
            session.commit()

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result["choices"][0]["message"]["content"]
        assert "highest" in content

    @pytest.mark.asyncio
    async def test_no_keys_available(self, fake_llm_server):
        base_url = fake_llm_server

        with Session(engine) as session:
            p = ProviderConfig(
                name="no-keys-provider",
                provider_type="custom",
                base_url=base_url,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            session.add(AgentRouteFallback(
                task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
            ))
            session.commit()

        with pytest.raises(RuntimeError, match="All fallback options exhausted"):
            await router.run_model(
                "TEST",
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_no_routes_for_task(self, fake_llm_server):
        with pytest.raises(ValueError, match="No routing configured for task 'NONEXISTENT'"):
            await router.run_model(
                "NONEXISTENT",
                messages=[{"role": "user", "content": "hi"}],
            )

    @pytest.mark.asyncio
    async def test_provider_without_provider_type_skipped(self, fake_llm_server):
        with Session(engine) as session:
            p = ProviderConfig(
                name="no-type-provider",
                provider_type=None,
                base_url=None,
                models="gpt-4",
            )
            session.add(p)
            session.flush()

            session.add(AgentRouteFallback(
                task_type="TEST", provider_id=p.id, models="gpt-4", priority=0
            ))
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

        with Session(engine) as session:
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

            session.add(AgentRouteFallback(
                task_type="TEST", provider_id=p.id, models="gpt-4,gpt-3.5", priority=0
            ))
            session.commit()

        result = await router.run_model(
            "TEST",
            messages=[{"role": "user", "content": "hi"}],
        )

        content = result["choices"][0]["message"]["content"]
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

        content = result["choices"][0]["message"]["content"]
        assert "test-key" in content
