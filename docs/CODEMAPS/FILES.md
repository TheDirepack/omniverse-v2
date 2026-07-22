# Omniverse V2 File Registry

**Last Updated:** 2026-07-21

This directory contains a comprehensive registry of key files and their purposes in the Omniverse V2 codebase.

## Directory Structure

```
omniverse-v2/
├── backend/                          # Python backend (FastAPI + LangGraph)
│   ├── app/                          # Main application package
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI entry point, router assembly
│   │   ├── agents/                   # Agent node implementations
│   │   ├── api/                      # HTTP API layer (/api/v1/)
│   │   │   ├── v1/                   # Versioned API endpoints
│   │   │   └── routers/              # DEPRECATED — commented out in main.py
│   │   ├── core/                     # Core engine utilities
│   │   ├── db/                       # Database schemas and sessions
│   │   ├── repositories/             # Data access layer
│   │   ├── research/                 # Research workflow
│   │   ├── services/                 # Business logic layer
│   │   ├── static/                   # Static assets
│   │   ├── templates/                # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── components/           # 47 reusable HTMX fragments
│   │   │   ├── fragments/
│   │   │   ├── layout/               # 3-panel layout system
│   │   │   ├── pages/                # 15 full-page templates
│   │   │   └── workflow/
│   │   └── views/                    # 11 HTMX view handlers
│   ├── tests/                        # Python tests
│   │   ├── backend/                  # 80+ unit/integration test files
│   │   ├── ui/                       # 21 HTMX E2E test files
│   │   ├── live/                     # 2 LLM behavioral test files
│   │   └── conftest.py
│   ├── data/                         # SQLite database files
│   ├── logs/                         # Agent log output
│   ├── scripts/                      # Utility scripts
│   └── pyproject.toml                # Python project config
├── docs/                             # Documentation
│   ├── CODEMAPS/                     # Architecture codemaps
│   ├── UI/                           # Design system specs
│   └── archive/                      # Historical docs
├── AGENTS.md                         # Agent documentation
├── README.md
├── CHANGELOG.md
├── run.sh                            # Application startup
├── test.sh                           # Test runner
├── lint.sh                           # Ruff linting
└── setup.sh                          # Environment setup
```

## Key Files by Category

### Entry Points

| File | Purpose |
| :--- | :--- |
| `backend/app/main.py` | FastAPI application entry point, router assembly |
| `backend/app/agents/nodes.py` | LangGraph node implementations |
| `backend/app/core/tools.py` | Agent tool definitions |
| `backend/app/db/schema.py` | Database table definitions |

### Agent Layer

| File | Purpose |
| :--- | :--- |
| `backend/app/agents/nodes.py` | LangGraph node definitions |
| `backend/app/agents/prompts/` | Modular system prompts for all agents |
| `backend/app/agents/prompt_templates.py` | Prompt template variables |
| `backend/app/agents/workflow.py` | Workflow configuration |
| `backend/app/agents/workflow_state.py` | OmniverseState schema |
| `backend/app/agents/agent_names.py` | Agent name constants |
| `backend/app/core/agent_engine.py` | Agent execution loop |
| `backend/app/core/tools.py` | Available agent tools |

### Research Pipeline

| File | Purpose |
| :--- | :--- |
| `backend/app/research/researcher.py` | Research agent implementation |
| `backend/app/research/summarizer.py` | Universe summarization |
| `backend/app/workflow/tiering_workflow.py` | Tiering state machine |
| `backend/app/workflow/extrapolation_workflow.py` | Extrapolation state machine |

### Data Access

| File | Purpose |
| :--- | :--- |
| `backend/app/repositories/universe.py` | Universe CRUD operations |
| `backend/app/repositories/tiering.py` | Tiering result storage |
| `backend/app/repositories/theory.py` | Theory persistence |
| `backend/app/repositories/settings.py` | Settings management |
| `backend/app/repositories/execution.py` | Execution state management |
| `backend/app/repositories/acquisition_cache.py` | Web artifact caching |

### Services

| File | Purpose |
| :--- | :--- |
| `backend/app/services/universe_service.py` | World management |
| `backend/app/services/execution_service.py` | Run lifecycle |
| `backend/app/services/tiering_service.py` | Power tiering logic |
| `backend/app/services/theory_service.py` | Extrapolation management |
| `backend/app/services/knowledge_retriever.py` | Graph queries |
| `backend/app/services/research_workspace.py` | Notebook management |
| `backend/app/services/settings_service.py` | Configuration management |
| `backend/app/services/provider_service.py` | LLM provider operations |
| `backend/app/services/effect_executor.py` | Tool call effect management |
| `backend/app/services/ocr_service.py` | Image-to-text extraction |

### Database

| File | Purpose |
| :--- | :--- |
| `backend/app/db/schema.py` | Main DB tables (17 tables) |
| `backend/app/db/notebook_schema.py` | Staging/Notebook DB (13 tables) |
| `backend/app/db/extrapolation_schema.py` | Extrapolation DB (1 table) |
| `backend/app/db/session.py` | Main DB session |
| `backend/app/db/settings_session.py` | Settings DB session |
| `backend/app/db/operational_session.py` | Operational DB session |
| `backend/app/db/notebook_session.py` | Notebook DB session |
| `backend/app/db/extrapolation_session.py` | Extrapolation DB session |

### HTMX Views

| File | Purpose |
| :--- | :--- |
| `backend/app/views/index.py` | Landing page |
| `backend/app/views/research.py` | Research views |
| `backend/app/views/research_results.py` | Research results viewer |
| `backend/app/views/worlds.py` | Universe views |
| `backend/app/views/knowledge.py` | Knowledge graph |
| `backend/app/views/settings.py` | Settings views (providers, routes, health) |
| `backend/app/views/logs.py` | Log viewer |
| `backend/app/views/provenance.py` | Evidence viewer |
| `backend/app/views/theory.py` | Theory viewer |
| `backend/app/views/validation.py` | Validation |
| `backend/app/views/flow.py` | Pipeline state |

### Core Engine

| File | Purpose |
| :--- | :--- |
| `backend/app/core/agent_engine.py` | Agent turn execution |
| `backend/app/core/router.py` | LLM provider routing & health |
| `backend/app/core/browser.py` | Cloakbrowser manager |
| `backend/app/core/tools.py` | Agent tool definitions |
| `backend/app/core/runtime_state.py` | ContextVar isolation |
| `backend/app/core/context_manager.py` | Token counting & pruning |
| `backend/app/core/context.py` | Universe context |
| `backend/app/core/domain.py` | ResearchTarget, ResearchWorkspace |
| `backend/app/core/web_search.py` | Search abstraction |
| `backend/app/core/web_fetch.py` | Page fetching |
| `backend/app/core/acquisition_cache.py` | Web result deduplication |
| `backend/app/core/agent_logger.py` | Structured logging |
| `backend/app/core/provider_models.py` | Provider/model schemas |
| `backend/app/core/templates.py` | Jinja2 configuration |
| `backend/app/core/importers/*.py` | OCR, Web page importers |

## Configuration Files

| File | Purpose |
| :--- | :--- |
| `backend/pyproject.toml` | Python dependencies and ruff/mypy config |
| `backend/requirements.txt` | Python dependencies |
| `backend/requirements-dev.txt` | Development dependencies |
| `backend/.env.local` | Environment variables |
| `pytest.ini` | pytest configuration |

## Utility Scripts

| File | Purpose |
| :--- | :--- |
| `setup.sh` | Environment setup |
| `run.sh` | Application startup |
| `test.sh` | Test runner |
| `lint.sh` | Ruff linting |

## Database Files

| File | Purpose |
| :--- | :--- |
| `backend/data/omniverse_v2.db` | Main knowledge graph |
| `backend/data/settings.db` | System configuration |
| `backend/data/operational.db` | Execution logs |
| `backend/data/notebook.db` | Research staging |
| `backend/data/extrapolation.db` | Speculative theories |
| `backend/data/acquisition.db` | Web artifact cache |

## Default Data

| File | Purpose |
| :--- | :--- |
| `backend/app/db/default_worlds.json` | Pre-seeded universes |

---

*Note: This registry reflects the current codebase structure.*
