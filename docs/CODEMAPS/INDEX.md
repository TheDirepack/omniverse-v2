# Omniverse V2 Codemaps Index

**Last Updated:** 2026-07-21

This directory contains the architectural and structural maps of the Omniverse V2 codebase. These maps are designed to provide a high-level understanding of the system's organization and data flow.

## Available Maps

- [[API_DOCS.md](API_DOCS.md)] - **API Documentation**: REST API (`/api/v1/`) and HTMX view route documentation with examples and deprecation notices.
- [[ARCHITECTURE.md](ARCHITECTURE.md)] - **System Architecture**: High-level overview of layered architecture, agents, database topology, and data flow.
- [[BACKEND.md](BACKEND.md)] - **Backend Module Map**: Detailed breakdown of FastAPI application, services, repositories, agents, workflows, core engine, and 11 HTMX view files.
- [[DATABASE.md](DATABASE.md)] - **Database Schema**: Complete schema for all 6 SQLite databases (Main, Settings, Operational, Notebook/Staging, Extrapolation, Acquisition).
- [[FRONTEND.md](FRONTEND.md)] - **Frontend Structure**: HTMX views, 15 page templates, 47 component templates, layout system, and settings JS architecture.
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
| Use the API | [API_DOCS.md](API_DOCS.md) |

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
| **API/Views** | `app/api/v1/`, `app/views/` | HTTP handling, HTMX rendering |
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
Main DB (Canon) ←→ Notebook DB (Research)
     ↓
Settings DB (Config) → Operational DB (Execution)
     ↓
Extrapolation DB (Speculation)
     ↓
Acquisition DB (Web Cache)
```

---

## Key Conventions

- **API Prefix**: `/api/v1/` for REST, direct view routes (`/settings/`, `/worlds/`, etc.) for HTMX
- **CORS**: Wide open (`*`)
- **DB Location**: `backend/data/` (overridable)
- **CSRF**: Removed (local dev tool)
- **HTMX**: Server-side rendered views (no React/Vue)
- **Log Format**: `[Timestamp] [Agent] [Model] [KeyID] [WorldName] [Type] Content`

## REST API Structure

- **`/api/v1/db/`** - Database operations (worlds, artifacts, notebook, claims)
- **`/api/v1/execution/`** - Execution & workflow (runs, logs, tiering, extrapolation)
- **`/api/v1/settings/`** - Configuration (providers, models, keys)
- **`/api/v1/tools/`** - Utility operations (worlds, research, registry)

Old `/api/` endpoints are commented out (see `main.py:129-136`).

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
| **HTMX 1.9.10** | Client-side DOM updates |
| **Tailwind CSS 3.4.17** | Utility-first CSS |

---

*Note: These maps are generated from the source code and should be updated whenever major architectural changes occur.*
