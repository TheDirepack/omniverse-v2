# Omniverse V2 Backend Module Map

**Last Updated:** 2026-07-11
**Entry Point:** `backend/app/main.py`

## Module Breakdown

This module provides a detailed breakdown of the FastAPI backend application, services, and agent orchestration.

---

## 1. API Layer (`backend/app/api/`)

**Purpose**: HTTP request handling, input validation, response formatting.

### Routers

| Router | File | Purpose | Key Endpoints |
| :--- | :--- | :--- | :--- |
| `worlds` | `routers/worlds.py` | Universe CRUD | `/api/worlds`, `/api/worlds/{id}`, `/api/worlds/{id}/tier` |
| `research` | `routers/research.py` | Research workflow | `/api/research/start`, `/api/research/status` |
| `runs` | `routers/runs.py` | Execution tracking | `/api/runs`, `/api/runs/{id}/abort` |
| `settings` | `routers/settings.py` | System config | `/api/settings`, `/api/settings/providers` |
| `providers` | `routers/providers.py` | LLM providers | `/api/providers` |
| `unconfirmed` | `routers/unconfirmed.py` | Staging DB | `/api/unconfirmed` |
| `routes` | `routers/routes.py` | Route management | `/api/routes` |

---

## 2. Service Layer (`backend/app/services/`)

**Purpose**: Business logic orchestration, state coordination, repository management.

### Core Services

| Service | File | Key Responsibilities |
| :--- | :--- | :--- |
| **Universe Service** | `universe_service.py` (25KB) | World CRUD, summary generation, `is_explored` tracking |
| **Execution Service** | `execution_service.py` | Run lifecycle, state transitions, abort handling |
| **Tiering Service** | `tiering_service.py` | Trigger tiering workflows, anomaly detection |
| **Theory Service** | `theory_service.py` | Speculative theory management |
| **Knowledge Retriever** | `knowledge_retriever.py` | Optimized artifact graph queries, pagination |
| **Research Workspace** | `research_workspace.py` | Notebook CRUD, source management, timeline events |
| **Settings Service** | `settings_service.py` (15KB) | Provider configs, agent routes, validation |
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
| **Agent Engine** | `agent_engine.py` (24KB) | Agent turn execution | `run_agent()`, Capability enum |
| **Router** | `router.py` (15KB) | LLM provider routing | `ModelRouter`, health checking, fallback chain |
| **Browser** | `browser.py` | Cloakbrowser management | `BrowserManager` singleton, Semaphore(5) |
| **Tools** | `tools.py` (1.3KB) | Agent tool definitions | `tool_web_search`, `tool_upsert_artifacts`, `tool_query_artifacts`, `tool_manage_source`, `tool_save_notebook_entry`, `tool_load_notebook_entry`, `tool_record_timeline_event` |
| **Runtime State** | `runtime_state.py` | ContextVar management | `run_id` isolation |
| **Web Search** | `web_search.py` | Search engine abstraction | `web_searcher` |
| **Web Fetch** | `web_fetch.py` (25KB) | Page fetching | `web_fetcher` |
| **Acquisition Cache** | `acquisition_cache.py` | Web result deduplication | Content hash caching |
| **Agent Logger** | `agent_logger.py` | Structured logging | `agent_logger` |
| **Provider Models** | `provider_models.py` | Provider schema | Provider, Model definitions |
| **Tools Importers** | `importers/*.py` | Tool result importers | `ocr_importer`, `web_page_importer` |

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
| **Schema** | `schema.py` | Main DB table definitions (Universe, Artifact, etc.) |
| **Unconfirmed** | `unconfirmed_schema.py` | Staging DB definitions |
| **Session** | `session.py` | DB session creation |
| **Settings Session** | `settings_session.py` | Settings DB session |
| **Operational Session** | `operational_session.py` | Operational DB session |
| **Extrapolation Session** | `extrapolation_session.py` | Extrapolation DB session |

---

## 9. Views Layer (`backend/app/views/`)

**Purpose**: HTMX-rendered server-side views.

| View | File | Purpose | Key Routes |
| :--- | :--- | :--- | :--- |
| **Index** | `index.py` | Landing page | `/`, `/settings` |
| **Research** | `research.py` | Research workflow | `/research/start`, `/research/status/{run_id}` |
| **Worlds** | `worlds.py` | Universe management | `/worlds`, `/worlds/new`, `/worlds/{id}/tier` |
| **Knowledge** | `knowledge.py` | Graph exploration | `/knowledge`, `/knowledge/artifacts` |
| **Settings** | `settings.py` | Provider config | `/settings/providers`, `/settings/routes` |
| **Logs** | `logs.py` | Execution monitoring | `/logs`, `/logs/{run_id}` |
| **Provenance** | `provenance.py` | Evidence tracking | `/provenance`, `/provenance/sources` |
| **Theory** | `theory.py` | Speculative theories | `/theory`, `/theory/new` |
| **Validation** | `validation.py` | Research validation | `/validation`, `/validation/artifacts` |
| **Flow** | `flow.py` | Pipeline visualization | `/flow`, `/flow/transitions` |

---

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Application                         │
│                   (main.py + routers)                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                            │
│              (services/*.py)                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Repository Layer (SQLModel)                    │
│            (repositories/*.py)                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                           │
│                  (db/*.py)                                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 Agent & Workflow Layer                      │
│       (agents/*.py + workflow/*.py)                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Core Engine                            │
│            (core/*.py + tools.py)                          │
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

---

*Last Updated: 2026-07-11*
