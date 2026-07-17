import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event as sa_event
from sqlmodel import Session, create_engine, select, text

# Use /dev/shm for RAM-disk speed in tests
SHM_DIR = Path("/dev/shm/omniverse_tests")
SHM_DIR.mkdir(exist_ok=True)

# Worker-specific DB suffixes for pytest-xdist
worker_id = os.getenv("PYTEST_XDIST_WORKER")
suffix = f"_{worker_id}" if worker_id else ""

# Test database URLs
DB_TIMEOUT = 60
TEST_DB_URL = f"sqlite:///{SHM_DIR}/omniverse_test{suffix}.db?timeout={DB_TIMEOUT}"
TEST_NOTEBOOK_URL = f"sqlite:///{SHM_DIR}/omniverse_test_notebook{suffix}.db?timeout={DB_TIMEOUT}"
TEST_EXTRAPOLATION_URL = f"sqlite:///{SHM_DIR}/omniverse_test_extrapolation{suffix}.db?timeout={DB_TIMEOUT}"
TEST_SETTINGS_URL = f"sqlite:///{SHM_DIR}/omniverse_test_settings{suffix}.db?timeout={DB_TIMEOUT}"
TEST_OPERATIONAL_URL = f"sqlite:///{SHM_DIR}/omniverse_test_operational{suffix}.db?timeout={DB_TIMEOUT}"

# Override env vars for tests BEFORE importing app
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["NOTEBOOK_DB_URL"] = TEST_NOTEBOOK_URL
os.environ["EXTRAPOLATION_DB_URL"] = TEST_EXTRAPOLATION_URL
os.environ["SETTINGS_DATABASE_URL"] = TEST_SETTINGS_URL
os.environ["OPERATIONAL_DATABASE_URL"] = TEST_OPERATIONAL_URL

from app.main import app


def _enable_fks(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create test engines
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
sa_event.listens_for(engine, "connect")(_enable_fks)
notebook_engine = create_engine(
    TEST_NOTEBOOK_URL, connect_args={"check_same_thread": False}
)
sa_event.listens_for(notebook_engine, "connect")(_enable_fks)
extrapolation_engine = create_engine(
    TEST_EXTRAPOLATION_URL, connect_args={"check_same_thread": False}
)
sa_event.listens_for(extrapolation_engine, "connect")(_enable_fks)
settings_engine = create_engine(
    TEST_SETTINGS_URL, connect_args={"check_same_thread": False}
)
sa_event.listens_for(settings_engine, "connect")(_enable_fks)
operational_engine = create_engine(
    TEST_OPERATIONAL_URL, connect_args={"check_same_thread": False}
)
sa_event.listens_for(operational_engine, "connect")(_enable_fks)


class _CSRFClient:
    def __init__(self, client: TestClient):
        self._client = client
        self._csrf_token: str | None = None
        self._init_csrf()

    def _init_csrf(self):
        _resp = self._client.get("/")
        csrf = self._client.cookies.get("csrf_token")
        if csrf:
            self._csrf_token = csrf

    def get(self, *args: Any, **kwargs: Any):
        return self._client.get(*args, **kwargs)

    def post(self, *args: Any, **kwargs: Any):
        headers = kwargs.pop("headers", {}) or {}
        if self._csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self._csrf_token
        return self._client.post(*args, headers=headers, **kwargs)

    def put(self, *args: Any, **kwargs: Any):
        headers = kwargs.pop("headers", {}) or {}
        if self._csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self._csrf_token
        return self._client.put(*args, headers=headers, **kwargs)

    def delete(self, *args: Any, **kwargs: Any):
        headers = kwargs.pop("headers", {}) or {}
        if self._csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self._csrf_token
        return self._client.delete(*args, headers=headers, **kwargs)

    def patch(self, *args: Any, **kwargs: Any):
        headers = kwargs.pop("headers", {}) or {}
        if self._csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self._csrf_token
        return self._client.patch(*args, headers=headers, **kwargs)

    def request(self, *args: Any, **kwargs: Any):
        headers = kwargs.pop("headers", {}) or {}
        if self._csrf_token and "X-CSRF-Token" not in headers:
            headers["X-CSRF-Token"] = self._csrf_token
        return self._client.request(*args, headers=headers, **kwargs)

    @property
    def cookies(self):
        return self._client.cookies


@pytest.fixture(scope="session", autouse=True)
def setup_databases():
    from app.db.session import init_db

    # First, create all tables across all DBs
    init_db()

    # Clean settings DB before seeding to remove stale data from past runs
    from sqlmodel import Session, text

    from app.db.settings_session import init_settings_db, settings_engine
    with Session(settings_engine) as s:
        s.execute(text("DELETE FROM agentroutefallback"))
        s.execute(text("DELETE FROM providerkey"))
        s.execute(text("DELETE FROM providerconfig"))
        s.execute(text("DELETE FROM setting"))
        s.commit()

    # Re-seed DEFAULT route after cleaning
    init_settings_db()
    yield

@pytest.fixture(scope="session", autouse=True)
def seed_providers(setup_databases):
    """Seeds the test settings DB with credentials from provider_config.py."""
    from sqlmodel import Session

    from app.db.schema import AgentRouteFallback, ProviderConfig, ProviderKey
    from app.db.settings_session import settings_engine
    from tests.provider_config import PROVIDER_CREDENTIALS

    with Session(settings_engine) as session:
        for provider_type, config in PROVIDER_CREDENTIALS.items():
            # 1. Upsert ProviderConfig
            provider = session.exec(
                select(ProviderConfig).where(ProviderConfig.name == provider_type)
            ).first()
            if not provider:
                provider = ProviderConfig(
                    name=provider_type,
                    provider_type=provider_type,
                    base_url=config.get("base_url"),
                    models=config.get("model"),
                )
                session.add(provider)
                session.flush()

            # 2. Upsert ProviderKey
            if config.get("api_key"):
                key = ProviderKey(
                    provider_id=provider.id,
                    api_key=config["api_key"],
                    priority=0,
                )
                session.add(key)

            # 3. Seed a route for common tasks to ensure they can use this provider
            # In a real system, this would be more complex.
            tasks = ["Researcher", "Logic Auditor", "DB Architect", "DEFAULT"]
            for task in tasks:
                fallback = AgentRouteFallback(
                    task_type=task,
                    priority=10,
                    provider_id=provider.id,
                    models=config.get("model"),
                )
                session.add(fallback)

        session.commit()

@pytest.fixture
def ephemeral_db(clean_db):
    return clean_db


@pytest.fixture
def api_client(client):
    return client


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield _CSRFClient(c)


@pytest.fixture
def session():
    with Session(engine) as session:
        yield session


@pytest.fixture
def clean_db(session):
    tables = [
        "artifactrelation", "artifact",
        "evidencechunk", "evidence",
        "worldtier", "anomaly", "universerelation",
        "modelconfig", "providerkey", "agentroutefallback",
        "providerconfig", "setting",
        "tiersystem",
        "universe", "executionstate",
    ]
    for t in tables:
        session.execute(text(f"DELETE FROM {t}"))
    session.commit()

    # Clean settings engine tables too
    from app.db.settings_session import settings_engine
    with Session(settings_engine) as ss:
        ss.execute(text("DELETE FROM agentroutefallback"))
        ss.execute(text("DELETE FROM providerkey"))
        ss.execute(text("DELETE FROM providerconfig"))
        ss.execute(text("DELETE FROM setting"))
        ss.commit()

    return session


@pytest.fixture
def _clean_db(clean_db):
    return clean_db


@pytest.fixture(autouse=True)
def _clear_acquisition_cache():
    from sqlmodel import Session, text

    from app.core import agent_engine as _ae
    from app.core.acquisition_cache import acquisition_cache
    from app.db.notebook_session import notebook_engine

    _ae._current_run_id = None

    acquisition_cache._lru.clear()
    acquisition_cache._pending.clear()

    repo = acquisition_cache.repo
    repo.session.exec(text("DELETE FROM provenance_edge"))
    repo.session.exec(text("DELETE FROM world_acquisition_usage"))
    repo.session.exec(text("DELETE FROM acquisition_artifact"))
    repo.session.commit()

    with Session(notebook_engine) as us:
        # Delete child tables first to avoid IntegrityError
        us.exec(text("DELETE FROM timeline_source"))
        us.exec(text("DELETE FROM timeline_participant"))
        us.exec(text("DELETE FROM timeline_location"))
        us.exec(text("DELETE FROM timeline_claim"))
        us.exec(text("DELETE FROM timeline_entry"))
        us.exec(text("DELETE FROM research_source"))
        us.exec(text("DELETE FROM notebook_entry"))
        us.exec(text("DELETE FROM provenance_edge"))
        us.exec(text("DELETE FROM world_acquisition_usage"))
        us.exec(text("DELETE FROM acquisition_artifact"))
        us.exec(text("DELETE FROM notebook_universe"))
        us.commit()

    yield


@pytest.fixture
def seeded_db(clean_db):
    from app.db.schema import Artifact, Universe
    session = clean_db
    u1 = Universe(name="U1", is_explored=True)
    session.add(u1)
    session.commit()
    session.refresh(u1)

    e1 = Artifact(name="E1", type="entity", universe_id=u1.id)
    session.add(e1)
    session.commit()

    return session, u1, e1, None


# --- Per-test log files, grouped by run ---

LOG_DIR = Path(__file__).parent / "logs"


def pytest_configure(config):
    LOG_DIR.mkdir(exist_ok=True)
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    config._test_run_dir = LOG_DIR / f"run_{run_ts}"
    config._test_run_dir.mkdir(exist_ok=True)


def pytest_runtest_setup(item):
    test_name = item.nodeid.replace("::", ".").replace("/", ".")
    run_dir = item.config._test_run_dir
    log_file = run_dir / f"{test_name}.log"
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    item._test_log_handler = handler
    item._test_log_file = log_file
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().addHandler(handler)


def pytest_runtest_teardown(item):
    handler = getattr(item, "_test_log_handler", None)
    if handler:
        logging.getLogger().removeHandler(handler)
        handler.close()


def pytest_sessionfinish(session):
    run_dir = getattr(session.config, "_test_run_dir", None)
    if run_dir and run_dir.exists():
        count = len(list(run_dir.glob("*.log")))
        print(f"\n[logs] {count} files written to {run_dir}/")
