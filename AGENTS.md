# Omniverse V2

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + React.

## Quick start

```sh
./setup.sh          # create venv, install deps, seed .env.local
./run.sh            # uvicorn backend :8000 + vite frontend :5173
./test.sh           # backend pytest + frontend vitest
```

Venvs: `backend/.venv/` or `backend/venv/` (both exist).

## Testing

```sh
./test.sh              # run all tests (standard)
./test.sh --slow       # run including LLM/network tests
./test.sh path/to/test.py  # run specific test file
```

Tests use ephemeral SQLite at `/tmp/omniverse_test.db`. Autouse fixture drops/recreates tables per test. `conftest.py` sets `DATABASE_URL` before importing app.
- Backend tests: root `tests/` (Python).
- Frontend tests: root `tests/` and `frontend/src/__tests__/` (Vitest).

## Architecture

### Backend Layered Structure
- `backend/app/api/` — FastAPI routers (entrypoints).
- `backend/app/services/` — Business logic (orchestrates repositories and workflows).
- `backend/app/repositories/` — Data access layer (SQLModel operations).
- `backend/app/agents/` — LangGraph node implementations and agent prompts.
- `backend/app/workflow/` — Specialized LangGraph state machines (Consolidation, Extrapolation, Tiering).
- `backend/app/research/` — High-level research agent logic.
- `backend/app/core/` — Low-level utilities (agent engine, tools, browser, router).
- `backend/app/db/` — Database schemas and session management.

### Knowledge Graph & Inference
- **Atomic Claims**: Knowledge is stored as triples (Subject $\rightarrow$ Predicate $\rightarrow$ Object).
- **Predicate Normalization**: Raw predicates are mapped to canonical forms via `PredicateService` (e.g., "uses" $\rightarrow$ `POWERED_BY`).
- **Typed Objects**: Objects are stored as either `object_entity_id` (pointer to another entity) or `object_literal` (text).
- **Technical Specs**: Specific values (e.g., jump range) are stored in `ClaimAttribute` linked to a claim.
- **Confidence Model**: derived from `support_count` (matching claims) and `contradiction_count` (conflicting claims).
- **Inference**: 
  - **Rule Discovery**: Scans for frequent predicate pairs $\rightarrow$ Proposer/Critic LLM loop $\rightarrow$ Human approval $\rightarrow$ `InferenceRule`.
  - **Materialization**: Applies approved rules to Claims to create `InferredClaim`s. Supports multi-hop composition up to `max_composition_depth`.
  - **Contradictions**: Flags inferences that contradict asserted claims for manual review.

### Frontend
- `frontend/src/` — React 18, Vite, vitest (node environment)

### DBs

- **Main DB**: SQLite via SQLModel at `DATABASE_URL` (default `omniverse_v2.db`). Stores the canonical Knowledge Graph (Entities and Claims).
- **Staging DB**: `unconfirmed.db` via `backend/app/db/unconfirmed_session.py`. Persistent research notes, leads, and unconfirmed claims.
- **Extrapolation DB**: `extrapolation.db` via `backend/app/db/extrapolation_session.py`. Isolated storage for speculative theories; must never contaminate canon DB.

### Pipeline (LangGraph state machine)

`research` $\rightarrow$ `db_integrator` $\rightarrow$ `summary` $\rightarrow$ `FINISHED`

- **Research**: Generic fact collection. No power-scaling analysis at this stage.
- **DB Integrator**: Stateful sequence (Integration $\rightarrow$ Cleanup).
  - **Integration**: DB Architect performs graph-based merging of verified claims (deduplication, contradiction detection, and technical attribute mapping) into Main DB.
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

- **Agent tool loop**: `core/agent_engine.py` supports stateful sessions. Includes a `min_turns` gate to prevent early submission.
- **Available tools**: `webSearch`, `fetchPage`, `compareSourceFreshness`, `queryClaims`, `upsertClaims`, `queryUnconfirmedClaims`, `saveUnconfirmedClaim`, `deleteUnconfirmedClaim`.


### Browser

`cloakbrowser` via `BrowserManager` singleton in `core/browser.py`. Semaphore(5). Started/stopped on FastAPI lifespan.

### State management

Global `ACTIVE_RUNS` / `ABORTED_RUNS` sets in `core/state.py`. Abort checked between every agent call. Universe context via `ContextVar` in `core/context.py`.

## Key conventions

- **API prefix**: all routes under `/api`.
- **CORS**: wide open (`*`).
- **pytest markers**: `slow` for LLM/network tests. `asyncio_mode = auto`.
- **Log Format**: `[Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content` (used for structured filtering in LogViewer).
- **Linting & Typechecking**: biome, tsc, Ruff, Mypy, Bandit, and Pylint are available.
- **Frontend tests**: in `src/__tests__/`.
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
    InferenceRulesPanel.tsx
    LogViewerPanel.tsx
    TheoriesPanel.tsx
    TraitViewerPanel.tsx
    settings/
      SettingsPanel.tsx    # tabs: providers, routing, general
      ProviderCard.tsx     # per-provider: type, base_url, models, API keys
      RoutingCard.tsx      # per-agent fallback chain, model select
      SettingItem.tsx      # key/value setting
```

## Maintenance Scripts
- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names in Main and Unconfirmed DBs.
