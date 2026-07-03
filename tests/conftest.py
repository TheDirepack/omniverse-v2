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


def _find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def real_server():
    db_path = BACKEND_DIR / "omniverse_v2.db"
    unconfirmed_path = BACKEND_DIR / "unconfirmed.db"
    json_path = BACKEND_DIR / "app" / "db" / "default_worlds.json"

    # Backup real DBs + default_worlds.json
    backups = {}
    for p in [db_path, unconfirmed_path, json_path]:
        if p.exists():
            bak = p.with_suffix(p.suffix + ".bak")
            shutil.copy2(p, bak)
            backups[p] = bak
            p.unlink()

    # Create seed DB
    from tests.test_db import create_test_db
    create_test_db(str(BACKEND_DIR))

    # Start uvicorn
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    # Strip DATABASE_URL so subprocess uses default (seed DB at cwd)
    subprocess_env = {
        k: v for k, v in os.environ.items() if k != "DATABASE_URL"
    }
    subprocess_env["UNCONFIRMED_DB_URL"] = "sqlite:////tmp/omniverse_test_unconfirmed.db"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "error"],
        cwd=str(BACKEND_DIR),
        env=subprocess_env,
    )

    # Health wait loop
    import httpx
    for _ in range(30):
        try:
            with httpx.Client() as c:
                r = c.get(f"{base_url}/api/health", timeout=1)
                if r.status_code == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        proc.kill()
        proc.wait(timeout=5)
        raise RuntimeError("Real server did not start")

    yield base_url

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)

    # Remove seed DB
    for p in [db_path, unconfirmed_path]:
        if p.exists():
            p.unlink()

    # Restore backups
    for orig, bak in backups.items():
        if bak.exists():
            shutil.move(str(bak), str(orig))


@pytest.fixture
def api_client(real_server):
    import httpx
    with httpx.Client(base_url=real_server) as c:
        yield c
