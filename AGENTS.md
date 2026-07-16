# Omniverse V2 - Agent Documentation

Multi-agent fictional power-tiering platform. FastAPI + LangGraph + HTMX.

---

## Quick Start

```sh
./setup.sh          # create venv, install deps, seed .env.local
./run.sh            # uvicorn backend :8000
./test.sh           # backend pytest
./lint.sh           # ruff
```

### Environments
- Backend venv: `backend/.venv/` or `backend/venv/`

---

## Testing

```sh
./test.sh              # run all tests (standard)
./test.sh --slow       # run including LLM/network tests
./test.sh --prompt-robustness  # run prompt failure mode & robustness tests
./test.sh path/to/test.py  # run specific test file
```

**Test Infrastructure:**
- Ephemeral SQLite at `/dev/shm/omniverse_tests/`
- Autouse fixture drops/recreates tables per test
- `conftest.py` sets `DATABASE_URL` before importing app

**Test Categories:**
- Backend tests: `backend/tests/backend/` (Python)
- UI tests: `backend/tests/ui/` (HTMX views)
- Prompt Robustness: `backend/tests/live/` (behavioral LLM tests)

---

## Linting

```sh
./lint.sh              # ruff (18 rule categories)
./lint.sh --strict     # + mypy, bandit, pylint
```

---

## Core Concepts

### Agent Engine (`backend/app/core/agent_engine.py`)

The `run_agent()` function orchestrates stateful agent sessions:

- **`run_id`**: Managed via `ContextVar` in `runtime_state.py` for task isolation
- **`min_turns`**: Gate preventing early submission before minimum turns
- **State Management**: Global `ACTIVE_RUNS` / `ABORTED_RUNS` sets in `core/state.py`
- **Context Isolation**: Universe context and `run_id` isolated via `ContextVar`
- **Capabilities**: Tool-based capability system (`READ_MAIN_DB`, `WRITE_MAIN_DB`, `READ_WORKSPACE`, `WRITE_WORKSPACE`, `ACQUISITION`, `SUBMIT`)

See [`core/agent_engine.py`](backend/app/core/agent_engine.py) for implementation details.

### Tool Loop

Agents execute a tool loop with these available tools:

| Tool | Purpose |
|------|---------|
| `webSearch` | Search web results |
| `fetchPage` | Fetch page content |
| `compareSourceFreshness` | Compare source recency |
| `queryArtifacts` | Query Knowledge Graph |
| `queryNotebookClaims` | Query notebook claims |
| `upsertArtifacts` | Upsert artifacts to DB |
| `deleteArtifact` | Delete artifacts |
| `saveNotebookEntry` | Save research to Staging DB |
| `loadNotebookEntry` | Load research from Staging DB |
| `deleteNotebookEntry` | Delete research entries |
| `deleteNotebookClaim` | Delete notebook claims |
| `manageSource` | Manage research sources |
| `recordTimelineEvent` | Record timeline events |
| `addTimelineDetail` | Add timeline details |
| `linkUniverses` | Link universes together |
| `linkEntityToCanonical` | Link entities to canonical versions |
| `ocrImage` | OCR image processing |
| `executePlan` | Execute multi-step plans |

See [`core/tools.py`](backend/app/core/tools.py) for tool definitions.

### LLM Routing

DB-driven fallback chain in [`core/router.py`](backend/app/core/router.py):
- `api_base` passed from `provider.base_url`
- Health checking and fallback logic

**Available Agents:**
- Researcher
- Universe Chronicler
- DB Architect
- Consolidator
- Tier Architect
- Logic Auditor
- Stability Unit
- Ontological Theorist
- Theoretical Auditor
- Rubric Steward

---

## Agent Layers

### Layer 1: Agents (`backend/app/agents/`)

LangGraph node implementations and prompts:

| File | Content |
|------|---------|
| `nodes.py` | Node implementations (`research_node`, `db_integrator_node`, `summary_node`, `manager_node`, `architecture_node`, `extrapolation_node`) |
| `prompts.py` | All agent system prompts and tool descriptions |
| `prompt_templates.py` | Dynamic prompt template variables |
| `workflow.py` | State machine definition |
| `workflow_state.py` | `OmniverseState` schema |
| `agent_names.py` | Agent name constants |

### Layer 2: Workflows (`backend/app/workflow/`)

Specialized LangGraph state machines:

| Workflow | File | Purpose |
|----------|------|---------|
| Tiering | `tiering_workflow.py` | Tier assignment rubric enforcement |
| Extrapolation | `extrapolation_workflow.py` | Speculative theory generation |

### Layer 3: Research (`backend/app/research/`)

High-level research workflow:

| Module | File | Purpose |
|--------|------|---------|
| Researcher | `researcher.py` | Research agent, iterative fact collection |
| Summarizer | `summarizer.py` | Universe summary from artifacts |

### Layer 4: Core (`backend/app/core/`)

Low-level utilities:

| Module | File | Purpose |
|--------|------|---------|
| Agent Engine | `agent_engine.py` | Turn execution, capabilities, context management |
| Router | `router.py` | LLM provider routing, health |
| Browser | `browser.py` | Cloakbrowser manager, Semaphore(5) |
| Tools | `tools.py` | Tool definitions |
| Runtime State | `runtime_state.py` | `run_id` ContextVar |
| Context Manager | `context_manager.py` | Token counting, context compression, pruning |
| Context | `context.py` | Universe context management |
| Domain | `domain.py` | ResearchTarget, ResearchWorkspace domain objects |
| Web Search | `web_search.py` | Search abstraction |
| Web Fetch | `web_fetch.py` | Page fetching |
| Acquisition Cache | `acquisition_cache.py` | Result deduplication |
| Agent Logger | `agent_logger.py` | Structured logging |
| Provider Models | `provider_models.py` | Provider/model schemas |
| Importers | `importers/*.py` | OCR, Web page extraction |

---

## Knowledge Graph

### Architecture

See [`docs/CODEMAPS/ARCHITECTURE.md`](docs/CODEMAPS/ARCHITECTURE.md) for system overview and high-level architecture.

### Database Schema

See [`docs/CODEMAPS/DATABASE.md`](docs/CODEMAPS/DATABASE.md) for complete schema details:

**Main Knowledge Graph:**
- **Universe**: Root entities with hierarchy support
- **Artifact**: Polymorphic knowledge units (Entity, Claim, Specification, Event)
- **ArtifactRelation**: Directed edges (e.g., `POWERED_BY`, `PART_OF`)
- **Evidence**: Knowledge grounding with source URLs and sections
- **EvidenceChunk**: Content segments for LLM window management
- **ArtifactVersion**: Full history of knowledge evolution
- **ArtifactType**: Type system definitions
- **TierSystem**: Tiering rubric definitions
- **WorldTier**: Tier assignments per universe
- **Anomaly**: Deviation records from rubric
- **UniverseRelation**: Inter-universe links

**Supporting Databases:**
- Settings DB: Provider configs, agent routes
- Operational DB: Execution logs, state
- Staging DB: Notebook workspace
- Extrapolation DB: Speculative theories (isolated)

### Knowledge Integration Flow

```
1. RESEARCH PHASE
   User Request → Researcher Agent
                ↓
           Web Search & Fetch
                ↓
           Notebook (Working Memory)
                ↓
           Verified Artifacts

2. DB INTEGRATION PHASE
   DB Architect Agent
                ↓
   Predicate Service (Normalization)
                ↓
   Main DB (Artifacts + Relations)

3. SUMMARY PHASE
   Universe Chronicler
                ↓
   Polished Summaries → Display

4. MARK EXPLORED
   Update `is_explored = True`
```

---

## Pipeline

### Research Pipeline (LangGraph)

```
manager → research → db_integrator → mark_explored → summary → FINISHED
```

See [`backend/app/agents/workflow.py`](backend/app/agents/workflow.py) for state machine definition.

**Nodes:**
- `research_node`: Fact collection
- `db_integrator_node`: DB integration
- `summary_node`: Summary generation
- `mark_explored_node`: Exploration flagging
- `manager_node`: Pipeline orchestration
- `architecture_node`: Workflow management (tiering)
- `extrapolation_node`: Speculative theory generation

---

## Manual Workflows

### Tiering

Manually triggered DB-wide pass:

1. **Stability Unit** slots worlds into persistent versioned rubric
2. **Outcomes:**
   - `STABLE`: Fits rubric
   - `ANOMALY`: Triggers rubric amendment
   - `INSUFFICIENT_DATA`: Leaves tier unchanged
3. **Reset Rule**: Re-researching resets `WorldTier` to untiered

See [`backend/app/workflow/tiering_workflow.py`](backend/app/workflow/tiering_workflow.py) for implementation.

### Extrapolation

Manually triggered, isolated from web tools:
- Reasons only from structured Main DB claims
- Uses [`backend/app/workflow/extrapolation_workflow.py`](backend/app/workflow/extrapolation_workflow.py)

---

## Key Conventions

- **API Prefix**: All routes under `/api`
- **CORS**: Wide open (`*`)
- **pytest markers**: `slow` for LLM/network tests; `asyncio_mode = auto`
- **Log Format**: `[Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content`
- **Log Viewer**: HTMX-based, tail-pagination (newest first)
- **Caching**: `AcquisitionCache` deduplicates web requests by content hash
- **Backend Entry**: `app/main.py`
- **Frontend**: HTMX views from `backend/app/views/` (no React, no Vite)
- **CSRF**: Removed (local dev tool)
- **DB Location**: `backend/data/` (overridable via env vars)
- **Context Management**: `ContextManager` handles token counting, context compression, and pruning of raw observations
- **Domain Objects**: `ResearchTarget` and `ResearchWorkspace` provide structured domain modeling
- **Artifact Versioning**: `ArtifactVersion` tracks history of knowledge evolution
- **Parallel Execution**: Batch processing controlled via `MAX_PARALLEL_AGENTS` setting

See [`docs/CODEMAPS/BACKEND.md`](docs/CODEMAPS/BACKEND.md) for detailed module breakdown.

---

## Maintenance Scripts

- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names

See [`docs/CODEMAPS/FILES.md`](docs/CODEMAPS/FILES.md) for complete file listing.

---

## Related Documentation

- [`docs/CODEMAPS/ARCHITECTURE.md`](docs/CODEMAPS/ARCHITECTURE.md) - System overview
- [`docs/CODEMAPS/BACKEND.md`](docs/CODEMAPS/BACKEND.md) - Detailed module breakdown
- [`docs/CODEMAPS/DATABASE.md`](docs/CODEMAPS/DATABASE.md) - Database schema
- [`docs/CODEMAPS/FRONTEND.md`](docs/CODEMAPS/FRONTEND.md) - HTMX views
- [`docs/CODEMAPS/INDEX.md`](docs/CODEMAPS/INDEX.md) - Index of all codemaps
