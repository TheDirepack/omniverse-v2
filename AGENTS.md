# Omniverse V2

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + React.

## Quick start

```sh
./setup.sh          # create venv, install deps, seed .env.local template
./run.sh            # uvicorn backend :8000 + vite frontend :5173
./test.sh           # backend pytest + frontend vitest
```

Venvs: `backend/.venv/` or `backend/venv/` (both exist).

## Testing

```sh
cd backend && python -m pytest tests/ -v --tb=short -m "not slow"
python -m pytest tests/ -v --tb=short -m "slow"   # LLM/network tests
cd frontend && npx vitest run
```

Tests use ephemeral SQLite at `/tmp/omniverse_test.db`. Autouse fixture drops/recreates tables per test. `conftest.py` sets `DATABASE_URL` before importing app.

## Architecture

### Backend Layered Structure
- `app/api/` — FastAPI routers (entrypoints).
- `app/services/` — Business logic (orchestrates repositories and workflows).
- `app/repositories/` — Data access layer (SQLModel operations).
- `app/agents/` — LangGraph node implementations and agent prompts.
- `app/workflow/` — Specialized LangGraph state machines (Consolidation, Extrapolation, Tiering).
- `app/research/` — High-level research agent logic.
- `app/core/` — Low-level utilities (agent engine, tools, browser, router).
- `app/db/` — Database schemas and session management.

### Frontend
- `frontend/src/` — React 18, Vite, vitest (node environment)

### DBs

- **Main DB**: SQLite via SQLModel at `DATABASE_URL` (default `omniverse_v2.db`). Stores verified canon facts.
- **Staging DB**: `unconfirmed.db` via `backend/app/db/unconfirmed_session.py`. Persistent research notes, leads, and unconfirmed facts.
- **Extrapolation DB**: `extrapolation.db` via `backend/app/db/extrapolation_session.py`. Isolated storage for speculative theories; must never contaminate canon DB.

### Pipeline (LangGraph state machine)

`research` $\rightarrow$ `db_integrator` $\rightarrow$ `summary` $\rightarrow$ `FINISHED`

- **Research**: Generic fact collection. No power-scaling analysis at this stage.
- **DB Integrator**: Stateful sequence (Integration $\rightarrow$ Cleanup).
  - **Integration**: DB Architect writes verified data to Main DB.
  - **Cleanup**: DB Architect removes promoted items from Staging DB.
  - **Security**: Write access to Main DB is stripped before the Cleanup phase begins.
- **Summary**: Regenerates world summary from Main DB traits.

### Tiering & Extrapolation (Manual Workflows)

- **Tiering**: Manually triggered DB-wide pass.
  - **Stability Unit**: Slots worlds into a persistent versioned rubric.
  - **Outcomes**: `STABLE`, `ANOMALY` (triggers rubric amendment), `INSUFFICIENT_DATA` (leaves tier unchanged).
  - **Reset Rule**: Re-researching a world always resets its `WorldTier` to untiered.
- **Extrapolation**: Manually triggered, isolated from web tools. Reasons only from structured Main DB traits.

### LLM routing

DB-driven fallback chain in `core/router.py`. `api_base` passed from `provider.base_url`. 
Agent names: Researcher, Universe Chronicler, DB Architect, Tier Architect, Logic Auditor, Stability Unit, Ontological Theorist, Theoretical Auditor.

### Agent tool loop

`core/agent_engine.py` — supports stateful sessions (history passing) to maintain context across prompt/tool shifts.
Available tools: `webSearch`, `fetchPage`, `queryTraits`, `upsertTrait`, `queryUnconfirmedTraits`, `saveUnconfirmedTrait`, `deleteUnconfirmedTrait`.

### Browser

`cloakbrowser` via `BrowserManager` singleton in `core/browser.py`. Semaphore(5). Started/stopped on FastAPI lifespan.

### State management

Global `ACTIVE_RUNS` / `ABORTED_RUNS` sets in `core/state.py`. Abort checked between every agent call. Universe context via `ContextVar` in `core/context.py`.

## Key conventions

- **API prefix**: all routes under `/api`.
- **CORS**: wide open (`*`).
- **pytest markers**: `slow` for LLM/network tests. `asyncio_mode = auto`.
- **No lint/typecheck/format scripts** in repo.
- **Frontend tests**: in `src/__tests__/`. Vitest with `node` environment.
- **Backend entry**: `app/main.py`.
- **Frontend entry**: `src/main.tsx`.
- **Vite proxy**: none (direct fetch to `localhost:8000` configured via `VITE_API_URL` env).

## Frontend structure

```
src/
  api.ts             # all fetch/API calls
  types.ts           # shared TypeScript types
  App.tsx            # root, routes to panels
  components/
    DashboardPanel.tsx
    DatabasePanel.tsx
    TheoriesPanel.tsx
    settings/
      SettingsPanel.tsx    # tabs: providers, routing, general
      ProviderCard.tsx     # per-provider: type, base_url, models, API keys
      RoutingCard.tsx      # per-agent fallback chain, model select
      SettingItem.tsx      # key/value setting
```
