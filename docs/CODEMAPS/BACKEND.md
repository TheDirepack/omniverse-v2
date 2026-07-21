# Omniverse V2 Backend Module Map

**Last Updated:** 2026-07-21
**Entry Point:** `backend/app/main.py`

## Module Breakdown

This module provides a detailed breakdown of the FastAPI backend application, services, and agent orchestration.

---

## 1. API Layer (`backend/app/api/`)

**Purpose**: HTTP request handling, input validation, response formatting.

### New API Structure (`/api/v1/`)

| Router | File | Purpose | Key Endpoints |
| :--- | :--- | :--- | :--- |
| `db/worlds` | `api/v1/db/worlds.py` | Universe CRUD | `/api/v1/db/worlds`, `/api/v1/db/worlds/by-uuid/{uuid}`, `/api/v1/db/worlds/{id}` |
| `db/artifacts` | `api/v1/db/artifacts.py` | Artifact CRUD | `/api/v1/db/artifacts`, `/api/v1/db/artifacts/{id}`, `/api/v1/db/artifacts/search` |
| `db/notebook` | `api/v1/db/notebook.py` | Notebook operations | `/api/v1/db/notebook/entries`, `/api/v1/db/notebook/entries/{id}` |
| `db/claims` | `api/v1/db/claims.py` | Knowledge claims | `/api/v1/db/claims/claims`, `/api/v1/db/claims/results`, `/api/v1/db/claims/theories` |
| `execution/runs` | `api/v1/execution/runs.py` | Execution tracking | `/api/v1/execution/runs/workflow`, `/api/v1/execution/runs/{id}`, `/api/v1/execution/runs/logs` |
| `settings/providers` | `api/v1/settings/__init__.py` | LLM providers | `/api/v1/settings/providers`, `/api/v1/settings/providers/{id}/models`, `/api/v1/settings/providers/{id}/keys` |
| `tools/worlds` | `api/v1/tools/__init__.py` | World management | `/api/v1/tools/worlds`, `/api/v1/tools/worlds/search`, `/api/v1/tools/worlds/registry` |

### Legacy Routers (Deprecated — Commented Out in main.py)

| Router | File | Purpose |
| :--- | :--- | :--- |
| `worlds` | `routers/worlds.py` | Universe CRUD |
| `research` | `routers/research.py` | Research workflow |
| `runs` | `routers/runs.py` | Execution tracking |
| `settings` | `routers/settings.py` | System config |
| `providers` | `routers/providers.py` | LLM providers |
| `notebook` | `routers/notebook.py` | Staging DB |
| `routes` | `routers/routes.py` | Route management |

Legacy routers are commented out in `main.py:129-136`. All functionality has been migrated to `/api/v1/` or HTMX view routes.

HTMX view routes are mounted separately in `main.py:110-120`:
```python
app.mount("/settings", ...)
app.mount("/worlds", ...)
app.mount("/research", ...)
```

---

## 2. Service Layer (`backend/app/services/`)

**Purpose**: Business logic orchestration, state coordination, repository management.

### Core Services

| Service | File | Key Responsibilities |
| :--- | :--- | :--- |
| **Universe Service** | `universe_service.py` | World CRUD, summary generation, `is_explored` tracking |
| **Execution Service** | `execution_service.py` | Run lifecycle, state transitions, abort handling |
| **Tiering Service** | `tiering_service.py` | Trigger tiering workflows, anomaly detection |
| **Theory Service** | `theory_service.py` | Speculative theory management |
| **Knowledge Retriever** | `knowledge_retriever.py` | Optimized artifact graph queries, pagination |
| **Research Workspace** | `research_workspace.py` | Notebook CRUD, source management, timeline events |
| **Settings Service** | `settings_service.py` | Provider configs, agent routes, validation |
| **Provider Service** | `provider_service.py` | LLM provider operations, model sync |
| **Effect Executor** | `effect_executor.py` | Tool call effect management |
| **OCR Service** | `ocr_service.py` | Image-to-text extraction |

---

## 3. Repository Layer (`backend/app/repositories/`)

**Purpose**: Pure data access layer using SQLModel ORM.

| Repository | File | Database Target | Key Operations |
| :--- | :--- | :--- | :--- |
| **Universe** | `universe.py` | Main DB | `get_by_ids()`, `upsert_artifacts()`, `query_claims()` |
| **Tiering** | `tiering.py` | Main DB | `get_tier()`, `update_tier()` |
| **Theory** | `theory.py` | Extrapolation DB | `get_theories()`, `upsert_theory()` |
| **Settings** | `settings.py` | Settings DB | `get_setting()`, `upsert_config()` |
| **Execution** | `execution.py` | Operational DB | `log_state()`, `get_transitions()` |
| **Acquisition Cache** | `acquisition_cache.py` | Acquisition DB | `get_by_url()`, `get_by_hash()`, `store()` |

---

## 4. Agent Layer (`backend/app/agents/`)

**Purpose**: LangGraph node implementations and agent prompts.

### Components

| File | Purpose | Key Content |
| :--- | :--- | :--- |
| `nodes.py` | Node implementations | `research_node`, `db_integrator_node`, `summary_node`, `mark_explored_node`, `manager_node`, `architecture_node`, `extrapolation_node` |
| `prompts.py` | System prompts | All agent system prompts, tool descriptions |
| `prompt_templates.py` | Template variables | Dynamic prompt content |
| `workflow.py` | Workflow config | State machine definition |
| `workflow_state.py` | State schema | `OmniverseState` definition |
| `agent_names.py` | Agent names | Agent name constants |

### Agent Pipeline

```
Manager → Research → DB Integrator → Mark Explored → Summary → Finished
```

---

## 5. Workflow Layer (`backend/app/workflow/`)

**Purpose**: Specialized LangGraph state machines.

| Workflow | File | Purpose |
| :--- | :--- | :--- |
| **Tiering** | `tiering_workflow.py` | Tier assignment rubric enforcement |
| **Extrapolation** | `extrapolation_workflow.py` | Speculative theory generation |

---

## 6. Core Engine (`backend/app/core/`)

**Purpose**: Low-level utilities, agent runtime, LLM routing.

### Core Modules

| Module | File | Purpose | Key Classes/Functions |
| :--- | :--- | :--- | :--- |
| **Agent Engine** | `agent_engine.py` | Agent turn execution | `run_agent()`, Capability enum |
| **Router** | `router.py` | LLM provider routing | `ModelRouter`, health checking, fallback chain |
| **Browser** | `browser.py` | Cloakbrowser management | `BrowserManager` singleton, Semaphore(5) |
| **Tools** | `tools.py` | Agent tool definitions | `webSearch`, `fetchPage`, `queryArtifacts`, `upsertArtifacts`, `saveNotebookEntry`, `loadNotebookEntry`, `readWorkspace`, `writeWorkspace`, `submitWork`, `recordTimelineEvent`, `manageSource`, `acquireArtifacts` |
| **Runtime State** | `runtime_state.py` | ContextVar management | `run_id` isolation |
| **Context Manager** | `context_manager.py` | Token counting & pruning | `ContextManager`, compression, pruning |
| **Context** | `context.py` | Universe context | Universe context management |
| **Domain** | `domain.py` | Domain objects | `ResearchTarget`, `ResearchWorkspace` |
| **Web Search** | `web_search.py` | Search engine abstraction | `web_searcher` |
| **Web Fetch** | `web_fetch.py` | Page fetching | `web_fetcher` |
| **Acquisition Cache** | `acquisition_cache.py` | Web result deduplication | Content hash + URL caching |
| **Agent Logger** | `agent_logger.py` | Structured logging | Rotating file logger |
| **Provider Models** | `provider_models.py` | Provider schema | Provider, Model definitions |
| **Templates** | `templates.py` | Jinja2 configuration | `Jinja2Templates` with auto-reload |
| **Importers** | `importers/*.py` | Tool result importers | OCR, Web page extraction |

---

## 7. Research Layer (`backend/app/research/`)

**Purpose**: High-level research workflow.

| Module | File | Purpose |
| :--- | :--- | :--- |
| **Researcher** | `researcher.py` | Research agent implementation, iterative fact collection |
| **Summarizer** | `summarizer.py` | Universe summary generation from artifacts |

---

## 8. Database Layer (`backend/app/db/`)

**Purpose**: Database schemas and session management.

| Module | File | Purpose |
| :--- | :--- | :--- |
| **Schema** | `schema.py` | Main DB table definitions (Universe, Artifact, etc.) — 17 tables |
| **Notebook Schema** | `notebook_schema.py` | Staging/Notebook DB — 13 tables |
| **Extrapolation Schema** | `extrapolation_schema.py` | Extrapolation DB — 1 table |
| **Session** | `session.py` | Main DB session creation |
| **Settings Session** | `settings_session.py` | Settings DB session |
| **Operational Session** | `operational_session.py` | Operational DB session |
| **Notebook Session** | `notebook_session.py` | Notebook/Staging DB session |
| **Extrapolation Session** | `extrapolation_session.py` | Extrapolation DB session |

---

## 9. Views Layer (`backend/app/views/`)

**Purpose**: HTMX-rendered server-side views.

| View | File | Purpose | Key Routes |
| :--- | :--- | :--- | :--- |
| **Index** | `index.py` | Landing page | `/` |
| **Research** | `research.py` | Research workflow | `/research`, `/research/choose-world` |
| **Research Results** | `research_results.py` | Results viewer | `/research/results/{run_id}` |
| **Worlds** | `worlds.py` | Universe management | `/worlds`, `/worlds/{uuid}/details` |
| **Knowledge** | `knowledge.py` | Graph exploration | `/knowledge`, `/knowledge/worlds` |
| **Settings** | `settings.py` | Provider config, routes, health | `/settings`, `/settings/tab/*` |
| **Logs** | `logs.py` | Execution monitoring | `/logs`, `/logs/{run_id}` |
| **Provenance** | `provenance.py` | Evidence tracking | `/provenance`, `/provenance/sources` |
| **Theory** | `theory.py` | Speculative theories | `/theory`, `/theory/{id}` |
| **Validation** | `validation.py` | Research validation | `/validation`, `/validation/artifacts` |
| **Flow** | `flow.py` | Pipeline visualization | `/flow`, `/flow/transitions` |

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                  Main Application (main.py)                  │
├─────────────────────┬───────────────────────────────────────┤
│   HTMX View Routes  │    API Routes (/api/v1/)              │
│   (views/*.py)      │    (api/v1/*.py)                      │
└──────────┬──────────┴──────────┬────────────────────────────┘
           │                     │
           ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│              (services/*.py)                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Repository Layer (SQLModel)                     │
│            (repositories/*.py)                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                            │
│                  (db/*.py)                                   │
├─────────────────────────────────────────────────────────────┤
│              Agent & Workflow Layer                          │
│       (agents/*.py + workflow/*.py)                          │
├─────────────────────────────────────────────────────────────┤
│                      Core Engine                             │
│            (core/*.py)                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Design Patterns

1. **Layered Architecture**: Clear separation of concerns
2. **Repository Pattern**: Data access abstraction
3. **Service Layer**: Business logic orchestration
4. **LangGraph**: Stateful agent workflows
5. **Provider Routing**: DB-driven LLM fallback chain
6. **Browser Manager**: Singleton with semaphore control
7. **Context Isolation**: `ContextVar` for `run_id`
8. **HTMX Views**: Server-rendered fragments with partial DOM updates

---

*Last Updated: 2026-07-21*
