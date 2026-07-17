# Omniverse V2 Codemaps Index

**Last Updated:** 2026-07-11

This directory contains the architectural and structural maps of the Omniverse V2 codebase. These maps are designed to provide a high-level understanding of the system's organization and data flow.

## Available Maps

- [[API_DOCS.md](API_DOCS.md)] - **API Documentation**: Complete REST API documentation with `/api/v1/` endpoints, examples, and deprecation notices.
- [[ARCHITECTURE.md](ARCHITECTURE.md)] - **System Architecture**: High-level overview of system components, layered architecture, data flow diagrams, and database topology.
- [[BACKEND.md](BACKEND.md)] - **Backend Module Map**: Detailed breakdown of FastAPI application, services, repositories, agents, workflows, and core engine modules.
- [[DATABASE.md](DATABASE.md)] - **Database Schema**: Complete schema documentation for all SQLite databases (Main, Settings, Operational, Staging, Extrapolation).
- [[FRONTEND.md](FRONTEND.md)] - **Frontend Structure**: HTMX views, server-rendered templates, and client-side integration.
- [[FILES.md](FILES.md)] - **File Registry**: Comprehensive directory structure, key files, and their purposes.

## Quick Navigation

### For New Developers
1. **ARCHITECTURE.md** → 2. **BACKEND.md** → 3. **DATABASE.md** → 4. **FRONTEND.md** → 5. **FILES.md**

### For Specific Tasks

| Task | Reference |
| :--- | :--- |
| Understand system architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Find module files | [BACKEND.md](BACKEND.md) |
| Query database | [DATABASE.md](DATABASE.md) |
| Build HTMX views | [FRONTEND.md](FRONTEND.md) |
| Locate any file | [FILES.md](FILES.md) |

---

## System Overview

### Entry Point
```python
# backend/app/main.py
app = FastAPI(title="Omniverse Tier List 2.0 API")
```

### Core Components

| Component | Location | Purpose |
| :--- | :--- | :--- |
| **API/Views** | `app/api/`, `app/views/` | HTTP handling, HTMX rendering |
| **Services** | `app/services/` | Business logic orchestration |
| **Repositories** | `app/repositories/` | Data access (SQLModel) |
| **Agents** | `app/agents/` | LangGraph node implementations |
| **Core** | `app/core/` | Agent engine, tools, routing |
| **Workflows** | `app/workflow/` | State machines |

### Research Pipeline
```
User → Researcher → Notebook → DB Architect → Main DB → Chronicler → Summary
```

### Database Isolation
```
Main DB (Canon) ←→ Staging DB (Research)
     ↓
Settings DB (Config)
     ↓
Operational DB (Execution)
     ↓
Extrapolation DB (Speculation)
```

---

## Key Conventions

- **API Prefix**: All routes under `/api/v1/` (versioned API)
- **CORS**: Wide open (`*`)
- **DB Location**: `backend/data/` (overridable)
- **CSRF**: Removed (local dev tool)
- **HTMX**: Server-side rendered views

## API Structure

- **`/api/v1/db/`** - Database operations (artifacts, notebook, claims)
- **`/api/v1/execution/`** - Execution & workflow (runs, logs, tiering, extrapolation)
- **`/api/v1/settings/`** - Configuration (providers, models, keys)
- **`/api/v1/tools/`** - Utility operations (worlds, research, registry)

Old `/api/` endpoints are deprecated.

---

## External Dependencies

| Dependency | Purpose |
| :--- | :--- |
| **FastAPI** | Web framework |
| **LangGraph** | Agent orchestration |
| **SQLModel** | ORM / Schema |
| **Cloakbrowser** | Stealth browsing |
| **Litellm** | LLM provider abstraction |
| **Pydantic** | Data validation |
| **Jinja2** | Templating |

---

*Note: These maps are generated from the source code and should be updated whenever major architectural changes occur.*
