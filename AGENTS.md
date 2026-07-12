# Omniverse V2

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + HTMX.

## Quick start

```sh
./setup.sh          # create venv, install deps, seed .env.local
./run.sh            # uvicorn backend :8000
./test.sh           # backend pytest
./lint.sh           # ruff
./lint.sh --strict  # + mypy, bandit, pylint
```

Venvs: `backend/.venv/` or `backend/venv/` (both exist).

## Testing

```sh
./test.sh              # run all tests (standard)
./test.sh --slow       # run including LLM/network tests
./test.sh --prompt-robustness  # run prompt failure mode & robustness tests
./test.sh path/to/test.py  # run specific test file
```

Tests use ephemeral SQLite at `/dev/shm/omniverse_tests/`. Autouse fixture drops/recreates tables per test. `conftest.py` sets `DATABASE_URL` before importing app.
- Backend tests: backend/tests/backend/ (Python).
- UI tests: backend/tests/ui/ (HTMX views).
- Prompt Robustness: Behavioral tests using real LLMs to verify prompt compliance and recovery from failure modes (found in backend/tests/live/test_prompt_failure_modes.py).

## Linting

```sh
./lint.sh              # ruff (18 rule categories, config in pyproject.toml)
./lint.sh --strict     # + mypy, bandit, pylint
```

## Architecture

### Backend Layered Structure
- `backend/app/api/` — FastAPI routers (entrypoints).
- `backend/app/services/` — Business logic (orchestrates repositories and workflows).
- `backend/app/repositories/` — Data access layer (SQLModel operations).
- `backend/app/agents/` — LangGraph node implementations and agent prompts.
- `backend/app/workflow/` — Specialized LangGraph state machines (DB Integration, Extrapolation, Tiering).
- `backend/app/research/` — High-level research agent logic.
- `backend/app/core/` — Low-level utilities (agent engine, tools, browser, router).
- `backend/app/db/` — Database schemas and session management.
- `backend/app/views/` — FastAPI routers for HTMX-rendered pages.

### Knowledge Graph & Provenance
- **Artifact-based Graph**: Knowledge is stored as a collection of polymorphic `Artifact`s (Entities, Claims, Specifications, and Events).
- **Predicate Normalization**: Raw predicates in claims are mapped to canonical forms via `PredicateService` (e.g., "uses" $\rightarrow$ `POWERED_BY`).
- **Provenance**: Every artifact is grounded in `Evidence` (source URLs and sections) via `evidence_refs`.
- **Versioning**: All changes to artifacts are archived in `ArtifactVersion` records, allowing for full historical traceability of knowledge evolution.
- **Confidence Model**: Derived from `support_count` (number of unique supporting evidence references).

### DBs

- **Main DB**: SQLite via SQLModel at `DATABASE_URL` (default `backend/data/omniverse_v2.db`). Stores the canonical Knowledge Graph (Artifacts and Relations).
- **Settings DB**: `backend/data/settings.db`. Agent routes, provider configs, settings.
- **Operational DB**: `backend/data/operational.db`. Execution state, logs.
- **Staging DB**: `backend/data/unconfirmed.db`. Persistent research workspace (Notebook entries, curated sources, and timelines).
- **Extrapolation DB**: `backend/data/extrapolation.db`. Isolated storage for speculative theories; must never contaminate canon DB.

All default to `backend/data/` but overridable via env vars.

### Pipeline (LangGraph state machine)

`research` $\rightarrow$ `db_integrator` $\rightarrow$ `summary` $\rightarrow$ `FINISHED`

- **Research**: Iterative fact collection and verification. The Researcher uses a `Notebook` as working memory and produces a structured JSON dataset of verified artifacts.
- **DB Integrator**: The `DB Architect` agent performs an intelligent merge of the verified research data into the Main DB, ensuring deduplication and provenance preservation.
- **Summary**: Regenerates world summary from the updated Main DB artifacts.
- Research artifacts are promoted directly to the Main DB; the research notebook persists as a record of the investigative process.

### Tiering & Extrapolation (Manual Workflows)

- **Tiering**: Manually triggered DB-wide pass.
  - **Stability Unit**: Slots worlds into a persistent versioned rubric.
  - **Outcomes**: `STABLE`, `ANOMALY` (triggers rubric amendment), `INSUFFICIENT_DATA` (leaves tier unchanged).
  - **Reset Rule**: Re-researching a world always resets its `WorldTier` to untiered.
- **Extrapolation**: Manually triggered, isolated from web tools. Reasons only from structured Main DB claims.

### LLM routing

DB-driven fallback chain in `core/router.py`. `api_base` passed from `provider.base_url`.
Agent names: Researcher, Universe Chronicler, DB Architect, Tier Architect, Logic Auditor, Stability Unit, Ontological Theorist, Theoretical Auditor.

- **Agent tool loop**: `core/agent_engine.py` supports stateful sessions. `run_id` is managed via `ContextVar` in `core/runtime_state.py` to ensure task-isolation and prevent race conditions during concurrent runs. Includes a `min_turns` gate to prevent early submission.
- **Available tools**: `webSearch`, `fetchPage`, `compareSourceFreshness`, `queryArtifacts`, `upsertArtifacts`, `saveNotebookEntry`, `loadNotebookEntry`, `deleteNotebookEntry`, `manageSource`, `recordTimelineEvent`.


### Browser

`cloakbrowser` via `BrowserManager` singleton in `core/browser.py`. Semaphore(5). Started/stopped on FastAPI lifespan.

### State management

Global `ACTIVE_RUNS` / `ABORTED_RUNS` sets in `core/state.py`. Abort checked between every agent call. Universe context and `run_id` are isolated via `ContextVar` in `core/context.py` and `core/runtime_state.py`.

## Key conventions

- **API prefix**: all routes under `/api`.
- **CORS**: wide open (`*`).
- **pytest markers**: `slow` for LLM/network tests. `asyncio_mode = auto`.
- **Log Format**: `[Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content` (used for structured filtering in LogViewer).
- **Log Viewer**: HTMX-based, tail-pagination (newest first), backend-driven filtering.
- **Caching**: `AcquisitionCache` deduplicates web requests by content hash; search results cached by composite key.
- **Linting**: `./lint.sh` — Ruff (18 rule categories). `./lint.sh --strict` — +Mypy, Bandit, Pylint.
- **Backend entry**: `app/main.py`.
- **Frontend**: HTMX views rendered from `backend/app/views/`. React frontend removed. Vite proxy: none.
- **CSRF**: Removed (local dev tool, cookie/header check added friction without proportional benefit).

## Maintenance Scripts
- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names in Main and Unconfirmed DBs.
