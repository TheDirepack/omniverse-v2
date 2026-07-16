# Omniverse V2 Frontend Codemap

**Last Updated:** 2026-07-16
**Entry Point:** `backend/app/views/`

## Overview

Omniverse V2 uses **HTMX** for its frontend, with views rendered server-side via FastAPI. There is no separate React/Vue frontend. All views are Python-based templates that support dynamic content injection via HTMX.

The frontend follows a component-based architecture with:
- **Pages**: Full-page templates (e.g., `research.html`, `world_details.html`)
- **Components**: Reusable HTMX fragments for partial updates
- **Layouts**: Base templates and layout wrappers

## Directory Structure

```
backend/app/views/
├── __init__.py
├── index.py          # Landing page
├── research.py       # Research workflow views (pages + components)
├── worlds.py         # Universe CRUD and management
├── knowledge.py      # Knowledge graph exploration
├── settings.py       # System configuration (providers, routes, health)
├── logs.py           # Execution logs and monitoring
├── provenance.py     # Evidence and source tracking
├── theory.py         # Speculative theories
├── validation.py     # Research validation
├── flow.py           # Pipeline state visualization

backend/app/templates/
├── base.html         # Base template with HTMX setup
├── components/       # Reusable HTMX fragments
│   ├── acquisition_panel.html
│   ├── active_runs_table.html
│   ├── artifact_detail.html
│   ├── artifact_list.html
│   ├── database_worlds.html
│   ├── entity_detail.html
│   ├── focused_search_panel.html
│   ├── log_list.html
│   ├── notebook_*.html (notebook components)
│   ├── provenance_trace.html
│   ├── provider_form.html
│   ├── research_*.html (research workspace components)
│   ├── route_form.html
│   ├── rule_item.html
│   ├── run_phase_details.html
│   ├── settings_*.html (settings components)
│   ├── theory_card.html
│   ├── world_*.html (world management components)
├── fragments/        # HTMX fragments
├── layout/           # Layout templates
├── pages/            # Full-page templates
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
- **Routes**:
  - `/settings` - General settings
  - `/settings/providers` - Provider management
  - `/settings/routes` - Agent route fallbacks
  - `/settings/health` - System health monitoring

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
Full-page templates with complete layouts:
- `index.html` - Landing page
- `research.html` - Research workspace
- `world_details.html` - Universe details with artifacts
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

### Components (`templates/components/`)
Reusable HTMX fragments for partial updates:
- **Acquisition**: `acquisition_panel.html`
- **Artifacts**: `artifact_detail.html`, `artifact_list.html`
- **Entities**: `entity_detail.html`
- **Notebook**: `research_notebook.html`, `research_notebook_entry.html`, `notebook_*.html`
- **Research**: `research_queue.html`, `focused_search_panel.html`, `research_sources.html`, `research_timeline.html`
- **Provenance**: `provenance_trace.html`
- **Settings**: `settings_general.html`, `settings_health.html`, `settings_providers.html`, `settings_routes.html`, `provider_form.html`
- **Worlds**: `world_list.html`, `world_detail.html`, `world_create_form.html`, `world_hierarchy.html`, `world_import_list.html`, `world_neighborhood.html`, `world_row.html`
- **Flow**: `flow_step.html`, `run_phase_details.html`
- **Log**: `log_list.html`
- **Route**: `route_form.html`, `_route_slot.html`, `rule_item.html`
- **Theory**: `theory_card.html`
- **Database**: `database_worlds.html`

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

- **HTMX** - Client-side DOM manipulation
- **Jinja2** - Server-side templating
- **FastAPI** - HTTP server
- **Cookies** - Active world state management (`active_world_id`)

## Key Patterns

### Cookie-Based State
- Active world ID stored in `active_world_id` cookie
- Workspace operations require active world context

### Fragment-Based Components
- Reusable HTML fragments for partial updates
- Components render data and HTMX triggers

### Background Task Integration
- Research runs execute via `BackgroundTasks`
- Results available at `/research/results/{run_id}`

### World Context
- `UniverseService` provides world CRUD operations
- World details include artifacts and notebook entries

## Related Areas

- **Backend Module Map** ([BACKEND.md](BACKEND.md)) - Service layer
- **Database Map** ([DATABASE.md](DATABASE.md)) - Data sources
- **Architecture Map** ([ARCHITECTURE.md](ARCHITECTURE.md)) - System overview
- **Agent Documentation** ([../..](../..)) - Agent engine and workflow

---

*Note: This frontend is server-rendered HTMX, not a separate SPA.*
