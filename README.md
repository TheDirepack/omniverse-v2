# Omniverse V2

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + HTMX.

## Quick Start

```sh
./setup.sh          # Create venv, install deps, create .env.local
./run.sh            # Start backend (uvicorn, :8000, hot-reload)
./run.sh --prod     # Start without hot-reload
./test.sh           # Run backend tests (pytest)
./test.sh --ui      # Include UI E2E browser tests
./test.sh --slow    # Include LLM/network tests
./lint.sh           # Ruff linter
./lint.sh --strict  # + mypy, bandit, pylint (if installed)
```

- Virtual environments: `backend/.venv/` or `backend/venv/`
- Environment config: `backend/.env.local`
- Requirements: `backend/requirements.txt`, `backend/requirements-dev.txt`

## Testing

Tests use ephemeral SQLite at `/dev/shm/omniverse_tests/`. An autouse fixture drops/recreates tables per test. `conftest.py` sets `DATABASE_URL` before importing the app.

| Command | What it runs |
|---|---|
| `./test.sh` | Backend unit/integration tests (fast, no network) |
| `./test.sh path/to/test.py` | Specific test file |
| `./test.sh --ui` | Include browser-based E2E tests via cloakbrowser |
| `./test.sh --slow` | Include tests needing LLM or network |
| `./test.sh --prompt-robustness` | Prompt failure mode & robustness tests |

**Test locations:**

- Backend tests: `backend/tests/backend/` (Python, unit/integration)
- UI/E2E tests: `backend/tests/ui/` (HTMX views, browser-based)
- Prompt robustness: `backend/tests/live/` (behavioral LLM tests)

## Linting

```sh
./lint.sh              # Ruff (config in backend/pyproject.toml)
./lint.sh --strict     # + mypy, bandit, pylint
```

## Architecture Highlights

For detailed architecture, see `AGENTS.md` and `docs/CODEMAPS/`.

- **Backend Layered Structure**: `api/`, `services/`, `repositories/`, `agents/`, `workflow/`, `research/`, `core/`, `db/`, `views/`
- **Knowledge Graph**: Artifact-based (Entities, Claims, Specifications, Events) with provenance via Evidence links and Artifact Versioning
- **Databases**: Main DB (`omniverse_v2.db`), Settings DB, Operational DB, Staging DB (notebook), Extrapolation DB — all in `backend/data/`
- **Pipeline (LangGraph)**: `research` → `db_integrator` → `summary` → `FINISHED`
- **LLM Routing**: DB-driven fallback chain in `core/router.py`
- **Browser**: `cloakbrowser` via `BrowserManager` singleton
- **State**: `ACTIVE_RUNS` / `ABORTED_RUNS` in `core/state.py`, `run_id` via `ContextVar`

## API

All routes under `/api/v1/`:

| Prefix | Area |
|---|---|
| `/api/v1/db/` | Database operations (artifacts, notebook, claims) |
| `/api/v1/execution/` | Execution & workflow (runs, logs, tiering, extrapolation) |
| `/api/v1/settings/` | Configuration (providers, models, keys) |
| `/api/v1/tools/` | Utility operations (worlds, research, registry) |

See [`docs/CODEMAPS/API_DOCS.md`](docs/CODEMAPS/API_DOCS.md) for complete docs with examples.

## Key Conventions

- **API Prefix**: All routes under `/api`
- **CORS**: Wide open (`*`) — local dev tool
- **pytest markers**: `slow` for LLM/network; `asyncio_mode = auto`
- **Log Format**: `[Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content`
- **Backend Entry**: `app/main.py`
- **Frontend**: HTMX views from `backend/app/views/` (no React, no Vite)
- **CSRF**: Removed (local dev tool)

## Maintenance Scripts

- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names
