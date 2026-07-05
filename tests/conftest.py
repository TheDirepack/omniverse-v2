import os
import atexit
import socket
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path

print("LOADING ROOT CONFTEX...")

# langchain-core eagerly imports pydantic.v1 which warns on Python 3.14+.
# No code uses pydantic v1 models — safe to suppress.
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with.*",
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="datetime.datetime.utcnow.*deprecated.*",
)

import pytest
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient

# Use temp file so worker threads in TestClient share same DB
TEST_DB_PATH = "/tmp/omniverse_test.db"

@atexit.register
def _cleanup():
    for p in [TEST_DB_PATH, "/tmp/omniverse_test_unconfirmed.db", "/tmp/omniverse_test_extrapolation.db"]:
        if os.path.exists(p):
            os.remove(p)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["UNCONFIRMED_DB_URL"] = "sqlite:////tmp/omniverse_test_unconfirmed.db"
os.environ["EXTRAPOLATION_DB_URL"] = "sqlite:////tmp/omniverse_test_extrapolation.db"

from app.db.session import engine
from app.db.unconfirmed_session import engine as unconfirmed_engine, init_unconfirmed_db
from app.db.unconfirmed_schema import unconfirmed_metadata
from app.db.extrapolation_session import engine as extrapolation_engine, init_extrapolation_db
from app.db.extrapolation_schema import extrapolation_metadata
from app.main import app




@pytest.fixture(autouse=True)
def auto_create_db():
    """Autouse: create tables before each test, drop after. Ensures clean slate."""
    SQLModel.metadata.create_all(engine)
    init_unconfirmed_db()
    init_extrapolation_db()
    yield
    SQLModel.metadata.drop_all(engine)
    unconfirmed_metadata.drop_all(unconfirmed_engine)
    extrapolation_metadata.drop_all(extrapolation_engine)

    # We don't explicitly drop unconfirmed tables here to avoid complexity, 
    # but since we use a temp file that is cleaned up at atexit, it's okay.


@pytest.fixture
def ephemeral_db():
    """Yields a session against the ephemeral DB. Tables already exist from autouse."""
    with Session(engine) as session:
        yield session


from unittest.mock import patch

@pytest.fixture
def client():
    """FastAPI TestClient against app with ephemeral DB.

    app startup normally calls init_db(), which (among other things) seeds
    ~150 default worlds from default_worlds.json. auto_create_db already
    creates a clean schema for every test, so we no-op init_db here to keep
    the DB genuinely empty by default -- tests that want seeded worlds add
    them explicitly.
    """
    with patch("app.main.init_db"):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def seeded_db(ephemeral_db):
    """DB with seeded Universe, ProviderConfig, AgentRouteFallback for FK tests."""
    from app.db.schema import Universe, ProviderConfig, AgentRouteFallback

    u = Universe(name="TestUniverse", summary="test summary", is_explored=False)
    ephemeral_db.add(u)
    ephemeral_db.commit()
    ephemeral_db.refresh(u)

    p = ProviderConfig(name="test-provider", provider_type="openai")
    ephemeral_db.add(p)
    ephemeral_db.commit()
    ephemeral_db.refresh(p)

    r = AgentRouteFallback(task_type="RESEARCH", provider_id=p.id, models="gpt-4")
    ephemeral_db.add(r)
    ephemeral_db.commit()
    ephemeral_db.refresh(r)

    return ephemeral_db, u, p, r


# ── Real server fixtures for test_routes.py ─────────────────────────

BACKEND_DIR = Path(__file__).parent.parent / "backend"
import uuid as _uuid


def _find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def real_server():
    """
    Spawns a real uvicorn server for integration tests.
    Each module gets its OWN seed DB path (uuid-suffixed) so modules
    cannot leak DB state into one another even when run concurrently.
    """
    run_id = _uuid.uuid4().hex[:8]

    # Module-local DB paths inside /tmp — no collision between modules
    module_db_path = Path(f"/tmp/omniverse_v2_{run_id}.db")
    module_unconfirmed_path = Path(f"/tmp/omniverse_test_unconfirmed_{run_id}.db")

    # Start uvicorn pointing at the module-local DB
    from tests.test_db import create_test_db
    create_test_db("/tmp", db_filename=f"omniverse_v2_{run_id}.db")
    
    port = _find_free_port()

    base_url = f"http://127.0.0.1:{port}"
    subprocess_env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    subprocess_env["DATABASE_URL"] = f"sqlite:///{module_db_path}"
    subprocess_env["UNCONFIRMED_DB_URL"] = f"sqlite:///{module_unconfirmed_path}"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "debug"],
        cwd=str(BACKEND_DIR),
        env=subprocess_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    # Health wait loop (allow up to 45 seconds for slow Playwright browser startup)
    import httpx
    for _ in range(90):
        try:
            with httpx.Client() as c:
                r = c.get(f"{base_url}/api/health", timeout=1)
                if r.status_code == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:
        # Read whatever was printed to stdout/stderr
        proc.kill()
        stdout_data, stderr_data = proc.communicate(timeout=5)
        raise RuntimeError(
            f"Real server did not start. Returncode: {proc.returncode}\n--- stdout ---\n{stdout_data}\n--- stderr ---\n{stderr_data}"
        )

    yield base_url

    # Teardown
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)

    # Remove module-local DBs
    for p in [module_db_path, module_unconfirmed_path]:
        if p.exists():
            p.unlink()



@pytest.fixture
def api_client(real_server):
    import httpx
    with httpx.Client(base_url=real_server) as c:
        yield c


# ── Real llama-server fixture for full-cycle inference-rule tests ──────
#
# Assumes `llama-server` (llama.cpp) is installed as a distro/system package
# and reachable on PATH -- this fixture does not attempt to build or fetch
# it. It also assumes the model file below is a REAL gguf, not the git-lfs
# pointer stub -- LFS blobs for this repo are hosted on
# github-cloud.githubusercontent.com, which is unreachable from some sandboxed
# CI environments even when github.com itself is reachable. In that case
# this fixture skips (not fails) so the rest of the suite still runs.

MODEL_PATH = Path(__file__).parent / "model" / "Qwen_Qwen3-0.6B-Q5_K_L.gguf"
MODEL_MIN_REAL_BYTES = 10 * 1024 * 1024  # LFS pointer stubs are ~130 bytes; real gguf is ~600MB


def _llama_server_available() -> tuple[bool, str]:
    if shutil.which("llama-server") is None:
        return False, "llama-server binary not found on PATH"
    if not MODEL_PATH.exists():
        return False, f"model file not found at {MODEL_PATH}"
    if MODEL_PATH.stat().st_size < MODEL_MIN_REAL_BYTES:
        return False, (
            f"{MODEL_PATH} is only {MODEL_PATH.stat().st_size} bytes -- looks like an "
            "unresolved git-lfs pointer, not the real model weights"
        )
    return True, ""


@pytest.fixture(scope="module")
def llama_server():
    """
    Launches a real llama-server subprocess against the Qwen3-0.6B model
    checked into tests/model/, exposing the OpenAI-compatible
    /v1/chat/completions endpoint the app's router already expects for
    provider_type="custom". Module-scoped since model load takes a few
    seconds and nothing in these tests needs a fresh process per test.

    Skips (rather than fails) if llama-server or a real model file isn't
    available, so `pytest -m "not slow"` runs (the default in CI) are
    unaffected either way.
    """
    available, reason = _llama_server_available()
    if not available:
        pytest.skip(f"Skipping real-model tests: {reason}")

    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        [
            "llama-server",
            "-m", str(MODEL_PATH),
            "-c", "4096",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--temp", "0",
            "-ngl", "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    import httpx
    for _ in range(120):  # up to 60s for cold model load on CPU
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"llama-server exited early (code {proc.returncode}):\n{output}")
        try:
            with httpx.Client() as c:
                r = c.get(f"{base_url}/health", timeout=1)
                if r.status_code == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        output = proc.stdout.read() if proc.stdout else ""
        raise RuntimeError(f"llama-server did not become healthy in time:\n{output}")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
