# Omniverse V2 Operations

Repository scripts select V2 paths and tests.

```sh
./setup.sh             # venv, dependencies, and backend/.env.local
./run.sh               # initialize V2, then Uvicorn with reload
./run.sh --prod        # initialize V2, then no reload
./test.sh              # backend/tests_v2; excludes network, slow, evaluation
./test.sh --ui         # backend/tests_v2/ui
./test.sh --slow       # includes slow; excludes network and evaluation
./test.sh --evaluation # includes evaluation; excludes network
./lint.sh
./lint.sh --strict
```

`run.sh` activates `backend/.venv` or `backend/venv`, exports `PYTHONPATH=backend`, loads `backend/.env.local`, normalizes relative V2 paths, runs `python -m app.v2.initialize`, then serves `app.main:app`.

## Initialization and lifecycle

Initialization refuses an unrecognized non-empty database, creates storage directories, upgrades with `backend/alembic-v2.ini`, imports the world seed, creates the Qwen default when needed, and validates the result.

```sh
PYTHONPATH=backend backend/.venv/bin/python -m app.v2.initialize
cd backend && ../backend/.venv/bin/alembic -c alembic-v2.ini upgrade head
```

Use your active virtual-environment path. Do not apply V2 migrations to a legacy database. Startup and periodic worker recovery reconcile stale leases. Shutdown waits for workers, closes adapters/HTTP/logging, and disposes SQLite.

Loopback-only binding is on by default. Set `OMNIVERSE_V2_REQUIRE_LOOPBACK=false` only when you intend to expose another host.

## JSONL logs

Database-backed logging settings enable these default streams:

```text
backend/logs/server.jsonl
backend/logs/agent.jsonl
backend/logs/remote-server.jsonl
```

Lines contain timestamp, stream, level, event type, component, correlations, and redacted data. Streams rotate by configured size with numbered backups. Log files use `0600`; directories use `0700`. Read server/agent logs through `GET /api/v2/logs/{stream}` or `/logs/`.

## Resets and tests

Use Settings reset controls for supported sections. Cancel or finish active runs before notebook, knowledge, or world resets. See [Persistence](PERSISTENCE.md#reset-boundaries). V2 tests use `backend/pytest-v2.ini`; focused tests work as `./test.sh backend/tests_v2/path/to_test.py`.
