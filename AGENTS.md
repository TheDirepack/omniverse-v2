# Omniverse V2 — Agent Instructions

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + HTMX.

## Commands

```sh
./setup.sh          # create venv, install deps, seed .env.local
./run.sh            # uvicorn backend:8000, hot-reload, sets PYTHONPATH
./run.sh --prod     # no reload
./test.sh           # pytest (excludes slow/network markers by default)
./test.sh --ui      # include HTMX E2E tests
./test.sh --slow    # include LLM/network tests
./lint.sh           # ruff check backend/app backend/tests
./lint.sh --strict  # + mypy / bandit / pylint (if installed in venv)
```

## Project Structure

- **Entrypoint**: `backend/app/main.py` — lifespan starts browser_manager, reconciles stale runs, validates settings
- **Venues**: `backend/.venv/` or `backend/venv/`
- **Env file**: `backend/.env.local` (not `.env` at root)
- **PYTHONPATH**: Must include `backend/` — `run.sh` does `export PYTHONPATH="$BASE_DIR/backend:$PYTHONPATH"`
- **Templates**: live in `backend/app/templates/` (NOT `backend/templates/` — that dir holds one stale file)
- **DBs**: 5 SQLite files in `backend/data/` — Main, Settings, Operational, Notebook (staging), Extrapolation
- **API v1**: mounted at `/api/v1/` — sub-routers: `/db/worlds`, `/db/artifacts`, `/db/notebook`, `/db/claims`, `/execution/runs`, `/settings`, `/tools`

### HTMX View Mount Points

| Prefix | View file | Purpose |
|--------|-----------|---------|
| `/` | `index.py` | Landing/dashboard |
| `/settings` | `settings.py` | Provider CRUD, routes, health, snapshots |
| `/worlds` | `worlds.py` | Universe list, detail, CRUD |
| `/research` | `research.py` | Research workflow (choose → run → results) |
| `/knowledge` | `knowledge.py` | Knowledge graph explorer |
| `/theory` | `theory.py` | Speculative theories |
| `/validation` | `validation.py` | Research validation |
| `/provenance` | `provenance.py` | Evidence / provenance |
| `/flow` | `flow.py` | Pipeline visualization |
| `/logs` | `logs.py` | Agent log viewer (tail-paginated, HTMX) |

### Dead / Unused Code

- `backend/app/api/routers/` — old API routers, all imports commented out in `main.py:20-28`
- `backend/app/views/research_results.py` — separate router NOT imported in `main.py`
- `backend/templates/pages/` — single stale file, templates live in `app/templates/`

## Testing

- **Autouse fixture** in `backend/tests/conftest.py` sets `DATABASE_URL` + 4 other DB env vars **before** importing `app.main`
- **Ephemeral SQLite** in `/dev/shm/omniverse_tests/` — worker-specific suffix for xdist support
- **Tables dropped/recreated per test** via `clean_db` + `_clear_acquisition_cache` fixtures
- **Seeded providers** from `tests/provider_config.py` (not `provider_config.py.example`)
- UI tests get a `_CSRFClient` wrapper — CSRF token auto-extracted from `/` response
- **pytest markers**: `slow` (LLM/network), `network` (external calls); default: `-m "not network and not slow"`
- Per-test log files written to `backend/tests/logs/run_<timestamp>/`
- Ruff per-file-ignores for tests: `ARG, TRY, ERA, PTH, SLOT, ASYNC`

## Framework / Toolchain Quirks

- **uvicorn `--reload` only watches `.py` files** — template changes need a manual browser refresh
- **Jinja2 `auto_reload = True`** (in `app/core/templates.py`) — but re-reads template on render only if `.py` file triggers uvicorn restart
- **HTMX 1.9.10** — `htmx.ajax(..., {values: formData})` with FormData causes 422; use plain JS objects for `values` instead
- **SQLModel** + multiple engines: each DB session module has its own `create_engine()` call (not one shared engine)
- **Cloakbrowser** managed via `BrowserManager` singleton with `Semaphore(5)` concurrency limit — started/stopped in lifespan
- **CORS**: wide open for `localhost:3000`, `127.0.0.1:3000`
- **CSRF**: removed (local dev tool) — but `conftest.py` `_CSRFClient` still adds the header for tests
- **pydantic-settings** used for some config

## Architecture Notes

- **Agent pipeline** (LangGraph): `manager → research → db_integrator → mark_explored → summary → FINISHED`
- **LLM routing**: DB-driven fallback chain in `core/router.py` — `api_base` from `provider.base_url`
- **State**: `ACTIVE_RUNS`/`ABORTED_RUNS` sets in `core/state.py`; `run_id` via `ContextVar`
- **Log format** (agents.log): `[timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content` — pipe-delimited, 10MB rotation × 5 backups
- **Log viewer** at `/logs/` — HTMX, tail-pagination (newest first), filterable by agent/world/model/event type/tool
- **Agent logging toggle**: Runtime setting `AGENT_LOGGING` in Settings DB (`"true"`/`"false"`)

## Conventions

- **API prefix**: `/api/v1/` for REST; direct view routes for HTMX
- **Frontend**: HTMX only — no React, no Vite, no npm build step
- **CORS**: open (`*`) — local dev tool
- **CSRF**: removed from app; test client handles it
