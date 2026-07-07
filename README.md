# Omniverse V2

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + HTMX.

## Quick Start

To get the project up and running:

```sh
./setup.sh          # Create virtual environment, install dependencies, seed .env.local
./run.sh            # Start the backend server (uvicorn backend :8000)
./test.sh           # Run backend pytest tests
./lint.sh           # Run ruff linter
./lint.sh --strict  # Run mypy, bandit, pylint
```

Virtual environments are located at `backend/.venv/` or `backend/venv/`.

## Testing

Tests utilize ephemeral SQLite at `/dev/shm/omniverse_tests/`. An autouse fixture handles table drops and recreations per test. `conftest.py` configures `DATABASE_URL` before importing the application.

```sh
./test.sh              # Run all standard tests
./test.sh --slow       # Run tests including LLM/network interactions
./test.sh path/to/test.py  # Run a specific test file
```

- Backend tests are located in `backend/tests/` (Python).
- Frontend (HTMX) views are tested via the backend.

## Linting

```sh
./lint.sh              # Ruff (18 rule categories, config in pyproject.toml)
./lint.sh --strict     # + mypy, bandit, pylint
```

## Architecture Highlights

For detailed architectural information, refer to `AGENTS.md`.

- **Backend Layered Structure**: Organized into `api/`, `services/`, `repositories/`, `agents/`, `workflow/`, `research/`, `core/`, `db/`, and `views/`.
- **Knowledge Graph & Inference**: Utilizes Atomic Claims (Subject -> Predicate -> Object), Predicate Normalization, Typed Objects, and a Confidence Model. Inference involves Rule Discovery and Materialization.
- **Databases**: Main DB (`backend/data/omniverse_v2.db`), Settings DB (`backend/data/settings.db`), Operational DB (`backend/data/operational.db`), Staging DB (`backend/data/unconfirmed.db`), Extrapolation DB (`backend/data/extrapolation.db`).
- **Pipeline (LangGraph)**: `research` -> `db_integrator` -> `summary` -> `FINISHED`. Traits replaced by Claims.
- **LLM Routing**: DB-driven fallback chain in `core/router.py` with various named agents.
- **Browser**: `cloakbrowser` via `BrowserManager` singleton.
- **State Management**: Global `ACTIVE_RUNS` / `ABORTED_RUNS` in `core/state.py`.

## Key Conventions

- **API Prefix**: All routes under `/api`.
- **CORS**: Wide open (`*`).
- **Pytest**: `slow` marker for LLM/network tests; `asyncio_mode = auto`.
- **Log Format**: `[Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content`.
- **Linting**: `./lint.sh` — Ruff (18 rule categories). `./lint.sh --strict` — +Mypy, Bandit, Pylint.
- **Backend Entry**: `app/main.py`.
- **Frontend**: HTMX views rendered from `backend/app/views/`. React frontend removed. Vite proxy: none.
- **CSRF**: Removed (local dev tool, cookie/header check added friction without proportional benefit).

## Maintenance Scripts

- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names in Main and Unconfirmed DBs.
