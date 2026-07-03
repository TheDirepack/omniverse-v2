import os
import atexit
import socket
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path

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
    for p in [TEST_DB_PATH, "/tmp/omniverse_test_unconfirmed.db"]:
        if os.path.exists(p):
            os.remove(p)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["UNCONFIRMED_DB_URL"] = "sqlite:////tmp/omniverse_test_unconfirmed.db"

from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def auto_create_db():
    """Autouse: create tables before each test, drop after. Ensures clean slate."""
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def ephemeral_db():
    """Yields a session against the ephemeral DB. Tables already exist from autouse."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client():
    """FastAPI TestClient against app with ephemeral DB."""
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
    module_db_path = BACKEND_DIR / f"omniverse_v2_{run_id}.db"
    module_unconfirmed_path = Path(f"/tmp/omniverse_test_unconfirmed_{run_id}.db")

    # Backup real production DB if it accidentally lives in BACKEND_DIR
    real_db_path = BACKEND_DIR / "omniverse_v2.db"
    real_db_bak = None
    if real_db_path.exists():
        real_db_bak = real_db_path.with_suffix(".db.bak")
        shutil.copy2(real_db_path, real_db_bak)

    # Create seed DB at the module-local path
    from tests.test_db import create_test_db
    create_test_db(str(BACKEND_DIR), db_filename=f"omniverse_v2_{run_id}.db")

    # Start uvicorn pointing at the module-local DB
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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

    # Restore production DB backup if we made one
    if real_db_bak and real_db_bak.exists():
        shutil.move(str(real_db_bak), str(real_db_path))


@pytest.fixture
def api_client(real_server):
    import httpx
    with httpx.Client(base_url=real_server) as c:
        yield c
