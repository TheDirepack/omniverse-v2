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
- **Staging DB**: `backend/data/notebook.db`. Persistent research workspace (Notebook entries, curated sources, and timelines).
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
- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names in Main and Staging DBs.

## Key Decisions

### Knowledge Page Redesign (3-Panel Layout)
- Replaced world dropdown + artifact list + inspector with 3-panel layout:
  - **Left panel**: Worlds list with artifact count badges, search-by-name, "Only with artifacts" checkbox filter
  - **Middle panel**: Artifact list for selected world (or global search results)
  - **Right panel**: Artifact detail/inspector with provenance
- Artifact search (`/api/artifacts/search`) and list (`/api/artifacts/list`) now support optional `universe_id` — when omitted, searches/returns all artifacts globally.
- `WorldList` fragment (`/knowledge/worlds`) computes artifact count per world via `GROUP BY` query; supports `q` (name search) and `has_artifacts` (boolean filter) params.

### Artifact API Template Fix
- `templates.TemplateResponse()` produced Jinja2 cache errors (`TypeError: cannot use 'tuple' as a dict key`). Switched all artifact endpoints to `HTMLResponse(content=template.render(...))`.
- Registered missing `json_decode` Jinja2 filter in `core/templates.py`.

### Route Form Model Selector
- Route form now shows all models from the selected provider as clickable toggle badges instead of a text/CSV input.
- Provider models embedded as `window.__providers` JSON in the route form template.
- Changing the provider dropdown auto-updates the model list.

### Misc UI Fixes
- Logs page dark mode: Added `dark:` variants to `logs.html` and `active_runs_table.html`.
- Create World form dark mode: Added `dark:` classes to `world_create_form.html`.
- Models badges: Added `<script>renderModelList();</script>` after hidden model inputs in `settings_providers.html`, `provider_form.html`, and `route_form.html` so badges render on initial load (not just after Sync/Add/Remove).
- `logs_list` hardcoded URL in `log_list.html` instead of `url_for('logs_list', ...)` because FastAPI included routers don't expose route names at the app level.

### Relevant Files
- `backend/app/views/knowledge.py` — `list_worlds` endpoint with `has_artifacts` filter, artifact counts
- `backend/app/templates/pages/knowledge.html` — 3-panel HTMX layout
- `backend/app/templates/fragments/world_list.html` — world rows with artifact count badges
- `backend/app/api/routers/artifacts.py` — optional `universe_id`, `HTMLResponse` pattern
- `backend/app/services/artifact_service.py` — `universe_id=None` support
- `backend/app/repositories/artifact.py` — `search_all_artifacts()` method
- `backend/app/core/templates.py` — `json_decode` filter
- `backend/app/templates/fragments/route_form.html` — provider model toggle badges
- `backend/app/views/logs.py` — added `name="logs_list"` to route (unused, URL hardcoded instead)
