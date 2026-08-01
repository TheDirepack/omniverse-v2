# Omniverse V2 — Agent Instructions

Research-first fictional-universe knowledge system. The deployed application uses FastAPI, SQLAlchemy, structured model routing, and HTMX.

## Deployed V2 Boundary

- **Entrypoint:** `backend/app/main.py` imports `create_app` from `backend/app/v2/main.py`.
- **Current runtime:** `backend/app/v2/`. The factory builds `V2Runtime`, serves static files, mounts unversioned HTML/HTMX views, and mounts the `/api/v2/` JSON router.
- **Legacy material:** `backend/app/api/`, `backend/app/views/`, `backend/app/services/`, `backend/app/workflow/`, and related templates remain in the repository as V1 source. They are not the deployed V2 runtime. Do not remove them unless a task explicitly requires it.
- **Canonical references:** Start with `docs/CODEMAPS_V2/INDEX.md`. `docs/CODEMAPS/` documents historical V1 only.

## Commands

```sh
./setup.sh          # create venv, install deps, seed .env.local
./run.sh            # uvicorn backend:8000, hot-reload, sets PYTHONPATH
./run.sh --prod     # no reload
./test.sh           # V2 tests; excludes network, slow, and evaluation markers
./test.sh --ui      # V2 browser UI tests
./test.sh --slow    # include slow tests; still excludes network and evaluation
./test.sh --evaluation # include evaluation tests; excludes network
./lint.sh           # Ruff
./lint.sh --strict  # Ruff, mypy, bandit, and pylint when installed
```

## Project Structure

- **Entrypoint**: `backend/app/main.py` → `backend/app/v2/main.py`
- **Venues**: `backend/.venv/` or `backend/venv/`
- **Env file**: `backend/.env.local` (not `.env` at root)
- **Runtime package**: `backend/app/v2/` holds configuration, runtime composition, persistence, acquisition, routing, workflow, worker, API, and views.
- **Templates**: V2 views render templates from `backend/app/templates/`.
- **Persistence**: V2 uses one Alembic-managed SQLite database, blobs, and protected credential storage under `backend/data/`.
- **API**: JSON endpoints use `/api/v2/`; HTML and HTMX routes are unversioned.
- **Initialization**: `run.sh` sets `PYTHONPATH=backend`, loads `backend/.env.local`, runs `python -m app.v2.initialize`, then serves `app.main:app`.

## Runtime and Research

- **Lifecycle**: the app lifespan starts the V2 runtime and optional worker, then waits for workers and closes adapters, HTTP clients, logging, and SQLite on shutdown.
- **Research workflow**: inventory, planning, search, acquisition, extraction, synthesis, audit, integration, and completion.
- **Evidence policy**: only accepted evidence with provenance may promote to canon. Workspace research remains provisional.
- **Model routing**: provider and model fallback is database-driven. Qwen is the normal final fallback; MiniCPM supports fetch/readability work.
- **Scope**: V2 covers research, evidence, canon, provenance, providers, and operations. Tiering and theory are deferred; `/theory/` is presentation-only.

## Testing and Operations

- **Tests**: V2 tests are in `backend/tests_v2/`, UI tests in `backend/tests_v2/ui/`, and configuration in `backend/pytest-v2.ini`.
- **Database safety**: initialization upgrades through `backend/alembic-v2.ini`. Never apply V2 migrations to a legacy database.
- **Logs**: inspect `backend/logs/server.jsonl`, `agent.jsonl`, and `remote-server.jsonl`, or use `/logs/` and `GET /api/v2/logs/{stream}`. Events include correlation data and redacted fields.
- **Network boundary**: loopback binding is required by default. Set `OMNIVERSE_V2_REQUIRE_LOOPBACK=false` only when intentional remote exposure is required.

## Conventions

- **API prefix**: `/api/v2/` for JSON; direct unversioned routes for HTMX.
- **Frontend**: server-rendered HTMX; no React, Vite, or npm build step.
- **Request correlation**: clients may supply a valid `X-Request-ID`; the middleware generates one otherwise and returns it in the response.
