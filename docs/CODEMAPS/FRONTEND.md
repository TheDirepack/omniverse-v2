# Omniverse V2 Frontend Codemap

**Last Updated:** 2026-07-21
**Entry Point:** `backend/app/views/`

## Overview

Omniverse V2 uses **HTMX** for its frontend, with views rendered server-side via FastAPI. There is no separate React/Vue frontend. All views are Python-based templates that support dynamic content injection via HTMX.

The frontend follows a component-based architecture with:
- **Pages**: Full-page templates (15 files)
- **Components**: Reusable HTMX fragments (47 files)
- **Layouts**: Base templates and layout wrappers

## Directory Structure

```
backend/app/views/
├── __init__.py
├── index.py              # Landing page
├── research.py           # Research workflow
├── research_results.py   # Research results viewer
├── worlds.py             # Universe CRUD and management
├── knowledge.py          # Knowledge graph exploration
├── settings.py           # System configuration (providers, routes, health)
├── logs.py               # Execution logs and monitoring
├── provenance.py         # Evidence and source tracking
├── theory.py             # Speculative theories
├── validation.py         # Research validation
├── flow.py               # Pipeline state visualization

backend/app/templates/
├── base.html             # Base template with HTMX + Tailwind CSS + dark mode
├── components/           # 47 reusable HTMX fragments
│   ├── acquisition_panel.html
│   ├── active_runs_table.html
│   ├── all_rules_updated.html
│   ├── artifact_detail.html
│   ├── artifact_list.html
│   ├── button.html
│   ├── database_worlds.html
│   ├── database_worlds_paginated.html
│   ├── entity_detail.html
│   ├── filter_popup.html
│   ├── flow_step.html
│   ├── focused_search_panel.html
│   ├── knowledge_notebook_tab.html
│   ├── knowledge_overview_tab.html
│   ├── knowledge_theory_tab.html
│   ├── knowledge_world_detail.html
│   ├── knowledge_world_list.html
│   ├── loading-spinner.html
│   ├── log_list.html
│   ├── notebook_artifact_card.html
│   ├── notebook_claim_card.html
│   ├── pagination.html
│   ├── provenance_trace.html
│   ├── provider_form.html
│   ├── research_history.html
│   ├── research_notebook.html
│   ├── research_notebook_entry.html
│   ├── research_queue.html
│   ├── research_sources.html
│   ├── research_timeline.html
│   ├── route_form.html
│   ├── rule_item.html
│   ├── run_phase_details.html
│   ├── settings_general.html
│   ├── settings_health.html
│   ├── settings_providers.html
│   ├── settings_routes.html
│   ├── theory_card.html
│   ├── world_create_form.html
│   ├── world_detail.html
│   ├── world_hierarchy.html
│   ├── world_import_list.html
│   ├── world_list.html
│   ├── world_neighborhood.html
│   ├── world_row.html
│   ├── world_snapshots.html
├── fragments/            # (empty — not in use)
├── layout/               # 3-panel layout system (3 files)
│   ├── 3_panel.html
│   ├── 3_panel_macro.html
│   └── 3_panel_structure.html
├── pages/                # 15 full-page templates
│   ├── choose_world.html
│   ├── error.html
│   ├── flow.html
│   ├── index.html
│   ├── knowledge.html
│   ├── logs.html
│   ├── provenance.html
│   ├── research.html
│   ├── research_results.html
│   ├── run_details.html
│   ├── settings.html
│   ├── theory.html
│   ├── validation.html
│   ├── world_details.html
│   └── worlds.html
└── workflow/             # Workflow-specific templates
    └── tiering/
        └── tiering.html
```

## Key Views

### Index (`index.py`)
- **Purpose**: Landing page
- **Routes**:
  - `/` - Main landing page

### Research (`research.py`)
- **Purpose**: Research workflow, workspace management, and focused search
- **Page Routes**:
  - `/research` - Main research page
  - `/research/choose-world` - World selection
  - `/research/results/{run_id}` - Research results
- **Component Routes**:
  - `/research/queue` - Active runs queue
  - `/research/focused-search` - Focused search panel
  - `/research/workspace/notebook` - Research notebook index
  - `/research/workspace/notebook/{entry_id}` - Notebook entry
  - `/research/workspace/sources` - Research sources
  - `/research/workspace/timeline` - Research timeline

### Research Results (`research_results.py`)
- **Purpose**: Dedicated research results viewer page
- **Routes**:
  - `/research/results/{run_id}` - Run results page
  - `/research/results/{run_id}/delete` - Delete run results

### API Integration

The frontend uses HTMX for dynamic updates and calls the new `/api/v1/` endpoints and HTMX view routes:

- **`/api/v1/tools/worlds`** - Add/search worlds via `/research/queue`
- **`/api/v1/execution/runs/workflow`** - Trigger research runs
- **`/api/v1/execution/runs/logs/{run_id}`** - Real-time log streaming
- **`/api/v1/db/claims/results`** - Display research results
- **`/api/v1/db/artifacts`** - Search and list artifacts
- **`/api/v1/settings/providers`** - Provider management API

Settings forms use HTMX view routes directly (not the API):
- `POST /settings/providers/upsert` — Create/update provider
- `POST /settings/providers/{id}/delete` — Delete provider
- `POST /settings/providers/{id}/keys` — Add API key
- `POST /settings/providers/{id}/sync` — Sync provider models
- `POST /settings/routes/upsert` — Create/update agent route
- `POST /settings/routes/{id}/delete` — Delete route
- `POST /settings/snapshots/create` — Create DB snapshot
- `DELETE /settings/snapshots/{id}` — Delete snapshot

### Worlds (`worlds.py`)
- **Purpose**: Universe management, CRUD, import, hierarchy
- **Page Routes**:
  - `/worlds` - Universe list
  - `/worlds/database-worlds` - Filtered universe list
  - `/worlds/{uuid}/details` - World details with artifacts and notebook
  - `/worlds/{uuid}/neighborhood` - Related universes
- **Component Routes**:
  - `/worlds/import` - World import list
  - `/worlds/create_fragment` - Create world form
  - `/worlds/graph` - Universe hierarchy graph
- **Post Routes**:
  - `POST /worlds/batch-research` - Batch research
  - `POST /worlds/{id}/toggle-explored` - Reset explored flag
  - `POST /worlds/{id}/delete` - Delete universe
  - `POST /worlds/delete-selected` - Bulk delete
  - `POST /worlds/import/{world_id}` - Import single world
  - `POST /worlds/import-all` - Import all available worlds
  - `POST /worlds/create` - Create universe
  - `POST /worlds/set-active-world` - Set active world cookie

### Knowledge (`knowledge.py`)
- **Purpose**: Knowledge graph exploration, artifact browsing
- **Page Routes**:
  - `/knowledge` - Main knowledge page
- **Component Routes**:
  - `/knowledge/worlds` - World list with artifact counts
  - `/knowledge/worlds/{world_id}` - World detail (entities, claims)
  - `/knowledge/worlds/{world_id}/children` - Child universes
  - `/knowledge/entities/{entity_id}` - Entity detail with claims

### Settings (`settings.py`)
- **Purpose**: LLM provider management, agent routing, system health
- **Tab Routes**:
  - `/settings/tab/general` - General settings
  - `/settings/tab/providers` - Provider management
  - `/settings/tab/routes` - Agent route fallbacks
  - `/settings/tab/health` - System health monitoring
- **Action Routes**:
  - `POST /settings/providers/upsert` — Create/update provider
  - `GET /settings/providers/{id}` — Get provider edit form
  - `GET /settings/providers/new` — Get new provider form
  - `POST /settings/providers/{id}/delete` — Delete provider
  - `POST /settings/providers/{id}/keys` — Add API key
  - `POST /settings/providers/{id}/sync` — Sync models
  - `POST /settings/routes/upsert` — Create/update route
  - `GET /settings/routes/{id}` — Get route edit form
  - `POST /settings/routes/{id}/delete` — Delete route
  - `POST /settings/general/update` — Update a setting
  - `POST /settings/general/delete/{key}` — Delete a setting
  - `POST /settings/reset-health` — Reset circuit breakers
  - `GET /settings/snapshots` — List snapshots fragment
  - `POST /settings/snapshots/create` — Create snapshot
  - `DELETE /settings/snapshots/{id}` — Delete snapshot
  - `POST /settings/snapshots/{id}/restore` — Restore snapshot

### Logs (`logs.py`)
- **Purpose**: Execution logs and monitoring
- **Page Routes**:
  - `/logs` - All execution logs
  - `/logs/{run_id}` - Run-specific logs
- **Component Routes**:
  - `/logs/filter` - Log filtering

### Provenance (`provenance.py`)
- **Purpose**: Evidence and source tracking
- **Routes**:
  - `/provenance` - Evidence explorer
  - `/provenance/sources` - Source management
  - `/provenance/evidence/{id}` - Evidence detail

### Theory (`theory.py`)
- **Purpose**: Speculative theory management
- **Routes**:
  - `/theory` - Browse theories
  - `/theory/{id}` - Theory detail

### Validation (`validation.py`)
- **Purpose**: Research validation workflow
- **Routes**:
  - `/validation` - Validation dashboard
  - `/validation/artifacts` - Validate artifacts

### Flow (`flow.py`)
- **Purpose**: Pipeline state visualization
- **Page Routes**:
  - `/flow` - Pipeline status
- **Component Routes**:
  - `/flow/transitions` - State transitions
  - `/flow/abort` - Abort active runs
  - `/flow/step` - Flow step details

## HTMX Integration

All views use HTMX for partial page updates via `hx-get`, `hx-post`, `hx-put`, `hx-delete`:

```python
@app.get("/research/queue", response_class=HTMLResponse)
async def research_queue(request: Request):
    """Active runs queue fragment"""
    template = templates.env.get_template("components/research_queue.html")
    return HTMLResponse(
        content=template.render(request=request, active_run_ids=active_run_ids)
    )
```

HTMX triggers common events via `HX-Trigger` headers:
```python
response.headers["HX-Trigger"] = (
    '{"showToast": {"value": "World imported", "type": "success"}}'
)
```

## Templates

### Pages (`templates/pages/`)
15 full-page templates with complete layouts:
- `index.html` - Landing page
- `research.html` - Research workspace
- `world_details.html` - Universe details with artifacts
- `worlds.html` - Universe list
- `knowledge.html` - Knowledge graph
- `settings.html` - System settings
- `logs.html` - Execution logs
- `provenance.html` - Evidence explorer
- `theory.html` - Speculative theories
- `validation.html` - Validation dashboard
- `flow.html` - Pipeline status
- `choose_world.html` - World selection
- `research_results.html` - Research results
- `run_details.html` - Run details
- `error.html` - Error page

### Components (`templates/components/`)
47 reusable HTMX fragments organized by domain:
- **Acquisition**: `acquisition_panel.html`
- **Artifacts**: `artifact_detail.html`, `artifact_list.html`
- **Entities**: `entity_detail.html`
- **Notebook**: `research_notebook.html`, `research_notebook_entry.html`, `notebook_artifact_card.html`, `notebook_claim_card.html`
- **Research**: `research_queue.html`, `focused_search_panel.html`, `research_sources.html`, `research_timeline.html`, `research_history.html`
- **Provenance**: `provenance_trace.html`
- **Settings**: `settings_general.html`, `settings_health.html`, `settings_providers.html`, `settings_routes.html`, `provider_form.html`
- **Worlds**: `world_list.html`, `world_detail.html`, `world_create_form.html`, `world_hierarchy.html`, `world_import_list.html`, `world_neighborhood.html`, `world_row.html`, `database_worlds.html`, `database_worlds_paginated.html`, `world_snapshots.html`
- **Flow**: `flow_step.html`, `run_phase_details.html`, `all_rules_updated.html`
- **Log**: `log_list.html`
- **Route**: `route_form.html`, `_route_slot.html`, `rule_item.html`
- **Theory**: `theory_card.html`
- **Knowledge**: `knowledge_world_list.html`, `knowledge_world_detail.html`, `knowledge_notebook_tab.html`, `knowledge_overview_tab.html`, `knowledge_theory_tab.html`
- **Utility**: `loading-spinner.html`, `pagination.html`, `button.html`, `filter_popup.html`

Note: `world_snapshots.html` is shared between the worlds and settings views and uses a `snapshot_url_prefix` template variable (e.g., `"/settings"` or `"/worlds"`) to generate correct HTMX URLs.

## Data Flow

```
User → HTMX Request (GET/POST) → FastAPI View → Template + Data → HTML Response
                                                 ↓
                                         HTMX Patch → Update DOM fragment
                                                 ↓
                                         HX-Trigger → Event handlers
```

## Static Assets

```
backend/app/static/
└── css/
    └── (empty - uses CDN or inline styles)
```

## External Dependencies

- **HTMX 1.9.10** - Client-side DOM manipulation
- **Jinja2** - Server-side templating
- **FastAPI** - HTTP server
- **Tailwind CSS 3.4.17** - Utility-first CSS (CDN for dev)
- **Cookies** - Active world state management (`active_world_id`)

## Key Patterns

### Cookie-Based State
- Active world ID stored in `active_world_id` cookie
- Workspace operations require active world context

### Fragment-Based Components
- Reusable HTML fragments for partial updates
- Components render data and HTMX triggers
- Snapshot management uses a shared `world_snapshots.html` template with configurable `snapshot_url_prefix`

### Background Task Integration
- Research runs execute via `BackgroundTasks`
- Results available at `/research/results/{run_id}`

### World Context
- `UniverseService` provides world CRUD operations
- World details include artifacts and notebook entries

### Settings JavaScript Architecture
- `settings.html` and `settings_providers.html` define global JS functions:
  - `selectProvider(id)` — Load provider edit form via `/settings/providers/{id}`
  - `selectRoute(id)` — Load route edit form via `/settings/routes/{id}`
  - `addProviderKey(providerId)` — Prompt for API key/priority, POST to `/settings/providers/{id}/keys`
  - `syncModels(providerId)` — Fetch sync via `/settings/providers/{id}/sync`
  - `addModel()` — Add model tag to provider form
  - `updateBaseUrl()` — Update hidden input when provider type changes
- Global error/retry handlers were removed in favor of HTMX's built-in `hx-on` and toast notifications

## Related Areas

- **Backend Module Map** ([BACKEND.md](BACKEND.md)) - Service layer
- **Database Map** ([DATABASE.md](DATABASE.md)) - Data sources
- **Architecture Map** ([ARCHITECTURE.md](ARCHITECTURE.md)) - System overview
- **Agent Documentation** ([AGENTS.md](../../AGENTS.md)) - Agent engine and workflow

---

*Note: This frontend is server-rendered HTMX, not a separate SPA.*
