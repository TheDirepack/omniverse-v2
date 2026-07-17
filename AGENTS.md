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
./test.sh                   # run all tests (standard, fast)
./test.sh --slow            # include LLM/network tests
./test.sh --ui              # include browser-based E2E tests
./test.sh --prompt-robustness  # run prompt failure mode & robustness tests
./test.sh path/to/test.py   # run specific test file
```

**Test Infrastructure:**
- Ephemeral SQLite at `/dev/shm/omniverse_tests/`
- Autouse fixture drops/recreates tables per test
- `conftest.py` sets `DATABASE_URL` before importing app

**Test Categories:**
- Backend tests: `backend/tests/backend/` (Python)
- UI/E2E tests: `backend/tests/ui/` (HTMX views + browser)
- Prompt Robustness: `backend/tests/live/` (behavioral LLM tests)

---

## Linting

```sh
./lint.sh              # ruff (config in backend/pyproject.toml)
./lint.sh --strict     # + mypy, bandit, pylint
```

---

## Scripts Reference

| Script | Purpose |
|---|---|
| `setup.sh` | Create venv, install deps, create `.env.local` |
| `run.sh` | Start uvicorn server (`--prod`, `--port=`, `--host=`, `--log-level=`, `--log-dir=`, `--log-file=`) |
| `test.sh` | Run pytest (`--ui`, `--slow`, `--prompt-robustness`, or pass pytest args) |
| `lint.sh` | Run ruff (`--strict` for mypy/bandit/pylint) |

---

## Logging

### Agent Logger

Structured file logging at `backend/logs/agents.log` (configurable). Each line is a pipe-delimited record:

```
[2026-07-17 10:00:00] [Researcher] [gpt-4o] [key1] [Star Wars] [THOUGHT] Analyzing the Force
```

Logged event types: `THOUGHT`, `TOOL_REQ`, `TOOL_RES`, `PROMPT`, `MODEL_CALL`, `ERROR`, `FAILED`, `INFO`, `WARNING`, `COMPLETED`, `IN_PROGRESS`, `STEP`.

### Log Viewer

HTMX-based at `/logs/` with tail-pagination (newest first) and filtering by agent, world, model, event type, tool, or free text.

### Configuration

Logging is configured at startup via environment variables, settable via `run.sh` flags:

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--log-level=LEVEL` | `APP_LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `--log-dir=DIR` | `APP_LOG_DIR` | `backend/logs/` | Directory for `agents.log` |
| `--log-file=FILE` | `APP_LOG_FILE` | `<dir>/agents.log` | Full path to log file (overrides `--log-dir`) |

**Examples:**

```sh
./run.sh --log-level=DEBUG                         # verbose agent logging
./run.sh --log-dir=/var/log/omniverse              # write logs elsewhere
./run.sh --log-file=/tmp/agent.log --log-level=WARNING  # custom path + level
```

The agent logger auto-rotates at 10MB, keeping 5 backups. The root Python logger uses the same `APP_LOG_LEVEL` level with format `[timestamp] [name] [LEVEL] message`.

**Toggle at runtime:** The `AGENT_LOGGING` setting in the Settings DB (`"true"`/`"false"`) controls whether agent log lines are written, independent of the log level.

---

## Core Concepts

### Agent Engine (`backend/app/core/agent_engine.py`)

The `run_agent()` function orchestrates stateful agent sessions:

- **`run_id`**: Managed via `ContextVar` in `runtime_state.py` for task isolation
- **`min_turns`**: Gate preventing early submission before minimum turns
- **State Management**: Global `ACTIVE_RUNS` / `ABORTED_RUNS` sets in `core/state.py`
- **Context Isolation**: Universe context and `run_id` isolated via `ContextVar`
- **Capabilities**: Tool-based capability system (`READ_MAIN_DB`, `WRITE_MAIN_DB`, `READ_WORKSPACE`, `WRITE_WORKSPACE`, `ACQUISITION`, `SUBMIT`)

See [`core/agent_engine.py`](backend/app/core/agent_engine.py).

### Tool Loop

Agents execute a tool loop with tools for web search, page fetch, knowledge graph queries, DB operations, notebook management, timeline events, and more.

See [`core/tools.py`](backend/app/core/tools.py) for tool definitions.

### LLM Routing

DB-driven fallback chain in [`core/router.py`](backend/app/core/router.py):
- `api_base` passed from `provider.base_url`
- Health checking and fallback logic

**Available Agents:**
- Researcher, Universe Chronicler, DB Architect, Consolidator, Tier Architect, Logic Auditor, Stability Unit, Ontological Theorist, Theoretical Auditor, Rubric Steward

---

## Agent Layers

### Layer 1: Agents (`backend/app/agents/`)

LangGraph node implementations and prompts:

| File | Content |
|------|---------|
| `nodes.py` | Node implementations |
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

| Module | File | Purpose |
|--------|------|---------|
| Researcher | `researcher.py` | Research agent, iterative fact collection |
| Summarizer | `summarizer.py` | Universe summary from artifacts |

### Layer 4: Core (`backend/app/core/`)

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

See [`docs/CODEMAPS/ARCHITECTURE.md`](docs/CODEMAPS/ARCHITECTURE.md) for system overview.

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
   User Request -> Researcher Agent
                -> Web Search & Fetch
                -> Notebook (Working Memory)
                -> Verified Artifacts

2. DB INTEGRATION PHASE
   DB Architect Agent -> Predicate Service (Normalization)
                      -> Main DB (Artifacts + Relations)

3. SUMMARY PHASE
   Universe Chronicler -> Polished Summaries -> Display

4. MARK EXPLORED
   Update `is_explored = True`
```

---

## Pipeline

### Research Pipeline (LangGraph)

```
manager -> research -> db_integrator -> mark_explored -> summary -> FINISHED
```

See [`backend/app/agents/workflow.py`](backend/app/agents/workflow.py).

---

## Manual Workflows

### Tiering

Manually triggered DB-wide pass:

1. **Stability Unit** slots worlds into persistent versioned rubric
2. **Outcomes**: `STABLE`, `ANOMALY`, `INSUFFICIENT_DATA`
3. **Reset Rule**: Re-researching resets `WorldTier` to untiered

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
- **Artifact Versioning**: `ArtifactVersion` tracks history of knowledge evolution
- **Parallel Execution**: Batch processing controlled via `MAX_PARALLEL_AGENTS` setting

---

## Maintenance Scripts

- `cleanup_worlds_general.py`: Strips trailing parentheses from universe names

---

## Related Documentation

- [`docs/CODEMAPS/ARCHITECTURE.md`](docs/CODEMAPS/ARCHITECTURE.md) - System overview
- [`docs/CODEMAPS/BACKEND.md`](docs/CODEMAPS/BACKEND.md) - Detailed module breakdown
- [`docs/CODEMAPS/DATABASE.md`](docs/CODEMAPS/DATABASE.md) - Database schema
- [`docs/CODEMAPS/FRONTEND.md`](docs/CODEMAPS/FRONTEND.md) - HTMX views
- [`docs/CODEMAPS/INDEX.md`](docs/CODEMAPS/INDEX.md) - Index of all codemaps
