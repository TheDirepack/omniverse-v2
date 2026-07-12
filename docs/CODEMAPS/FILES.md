# Omniverse V2 File Registry

**Last Updated:** 2026-07-11

This directory contains a comprehensive registry of key files and their purposes in the Omniverse V2 codebase.

## Directory Structure

```
omniverse-v2/
├── backend/                          # Python backend (FastAPI + LangGraph)
│   ├── app/                          # Main application package
│   │   ├── api/                      # HTTP API layer
│   │   │   ├── routers/              # API route handlers
│   │   │   └── __init__.py
│   │   ├── agents/                   # Agent node implementations
│   │   │   ├── nodes.py              # LangGraph node definitions
│   │   │   ├── prompts.py            # Agent system prompts
│   │   │   ├── prompt_templates.py   # Template variables
│   │   │   ├── workflow.py           # Workflow configuration
│   │   │   └── workflow_state.py     # State schema
│   │   ├── api/                      # API routes
│   │   ├── core/                     # Core engine utilities
│   │   │   ├── agent_engine.py       # Agent loop execution
│   │   │   ├── browser.py            # Browser manager (Cloakbrowser)
│   │   │   ├── router.py             # LLM provider routing
│   │   │   ├── tools.py              # Agent tools
│   │   │   ├── runtime_state.py      # Context variables
│   │   │   └── web_search.py         # Search utilities
│   │   ├── db/                       # Database schemas
│   │   │   ├── schema.py             # Main DB models
│   │   │   ├── unconfirmed_schema.py # Staging DB models
│   │   │   └── session.py            # DB session management
│   │   ├── repositories/             # Data access layer
│   │   │   ├── universe.py           # Universe operations
│   │   │   ├── tiering.py            # Tiering operations
│   │   │   ├── theory.py             # Theory operations
│   │   │   ├── settings.py           # Settings operations
│   │   │   └── execution.py          # Execution operations
│   │   ├── services/                 # Business logic layer
│   │   │   ├── universe_service.py   # World lifecycle
│   │   │   ├── execution_service.py  # Run management
│   │   │   ├── tiering_service.py    # Power tiering
│   │   │   ├── theory_service.py     # Extrapolation
│   │   │   ├── knowledge_retriever.py# Graph querying
│   │   │   ├── research_workspace.py # Research notebook
│   │   │   └── settings_service.py   # Config management
│   │   ├── research/                 # Research workflow
│   │   │   ├── researcher.py         # Research agent
│   │   │   └── summarizer.py         # Summary generation
│   │   ├── workflow/                 # LangGraph workflows
│   │   │   ├── tiering_workflow.py   # Tiering state machine
│   │   │   └── extrapolation_workflow.py # Extrapolation
│   │   ├── views/                    # HTMX views
│   │   │   ├── index.py              # Landing page
│   │   │   ├── research.py           # Research views
│   │   │   ├── worlds.py             # Universe views
│   │   │   ├── knowledge.py          # Knowledge graph
│   │   │   ├── settings.py           # Settings views
│   │   │   ├── logs.py               # Log viewer
│   │   │   ├── provenance.py         # Evidence viewer
│   │   │   ├── theory.py             # Theory viewer
│   │   │   ├── validation.py         # Validation
│   │   │   ├── inference.py          # Inference
│   │   │   └── flow.py               # Pipeline state
│   │   ├── main.py                   # FastAPI entry point
│   │   └── __init__.py
│   ├── tests/                       # Python tests
│   ├── data/                        # Database files
│   ├── scripts/                     # Utility scripts
│   └── pyproject.toml               # Python project config
└── docs/CODEMAPS/                   # Generated documentation
    ├── INDEX.md
    ├── ARCHITECTURE.md
    ├── BACKEND.md
    ├── DATABASE.md
    ├── FRONTEND.md
    └── FILES.md
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
| `backend/app/agents/prompts.py` | System prompts for all agents |
| `backend/app/agents/prompt_templates.py` | Prompt template variables |
| `backend/app/agents/workflow.py` | Workflow configuration |
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

### Services

| File | Purpose |
| :--- | :--- |
| `backend/app/services/universe_service.py` | World management |
| `backend/app/services/execution_service.py` | Run lifecycle |
| `backend/app/services/tiering_service.py` | Power tiering logic |
| `backend/app/services/knowledge_retriever.py` | Graph queries |
| `backend/app/services/research_workspace.py` | Notebook management |

### Database

| File | Purpose |
| :--- | :--- |
| `backend/app/db/schema.py` | Main DB tables |
| `backend/app/db/unconfirmed_schema.py` | Staging DB tables |
| `backend/app/db/session.py` | Session management |

### Views

| File | Purpose |
| :--- | :--- |
| `backend/app/views/index.py` | Landing page |
| `backend/app/views/research.py` | Research views |
| `backend/app/views/worlds.py` | Universe views |
| `backend/app/views/knowledge.py` | Knowledge graph |
| `backend/app/views/logs.py` | Log viewer |
| `backend/app/views/provenance.py` | Evidence viewer |

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
| `lint.sh` | Linting |

## Database Files

| File | Purpose |
| :--- | :--- |
| `backend/data/omniverse_v2.db` | Main knowledge graph |
| `backend/data/settings.db` | System configuration |
| `backend/data/operational.db` | Execution logs |
| `backend/data/unconfirmed.db` | Research staging |
| `backend/data/extrapolation.db` | Speculative theories |

## Default Data

| File | Purpose |
| :--- | :--- |
| `backend/app/db/default_worlds.json` | Pre-seeded universes |

---

*Note: This registry is auto-generated from the codebase structure.*
