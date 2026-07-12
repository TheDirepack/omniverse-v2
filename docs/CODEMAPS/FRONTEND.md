# Omniverse V2 Frontend Codemap

**Last Updated:** 2026-07-11
**Entry Point:** `backend/app/views/`

## Overview

Omniverse V2 uses **HTMX** for its frontend, with views rendered server-side via FastAPI. There is no separate React/Vue frontend. All views are Python-based templates that support dynamic content injection via HTMX.

## Directory Structure

```
backend/app/views/
├── __init__.py
├── index.py          # Landing page and research initiation
├── research.py       # Research workflow views
├── worlds.py         # Universe CRUD and tiering
├── knowledge.py      # Knowledge graph exploration
├── settings.py       # System configuration
├── logs.py           # Execution logs and monitoring
├── provenance.py     # Evidence and source tracking
├── theory.py         # Speculative theories
├── validation.py     # Research validation
├── flow.py           # Pipeline state visualization
```

## View Components

### 1. Index Views (`index.py`)
- **Purpose**: Landing page, user authentication, research initiation
- **Key Routes**:
  - `/` - Main landing page
  - `/settings` - Global settings

### 2. Research Views (`research.py`)
- **Purpose**: Research workflow visualization and control
- **Key Routes**:
  - `/research/start` - Initiate new research run
  - `/research/status/{run_id}` - View research progress
  - `/research/logs/{run_id}` - View agent logs

### 3. World Views (`worlds.py`)
- **Purpose**: Universe management and tiering
- **Key Routes**:
  - `/worlds` - List all universes
  - `/worlds/new` - Create new universe
  - `/worlds/{id}/tier` - Tier a universe
  - `/worlds/{id}/explore` - Explore/universe detail

### 4. Knowledge Views (`knowledge.py`)
- **Purpose**: Knowledge graph exploration
- **Key Routes**:
  - `/knowledge` - Graph visualization
  - `/knowledge/artifacts` - Browse artifacts
  - `/knowledge/artifacts/{id}` - Artifact detail

### 5. Settings Views (`settings.py`)
- **Purpose**: Provider configuration and agent routing
- **Key Routes**:
  - `/settings/providers` - LLM provider management
  - `/settings/routes` - Agent route fallbacks
  - `/settings/agents` - Agent configuration

### 6. Logs Views (`logs.py`)
- **Purpose**: Execution state monitoring
- **Key Routes**:
  - `/logs` - View all execution logs
  - `/logs/{run_id}` - Run-specific logs
  - `/logs/filter` - Log filtering

### 7. Provenance Views (`provenance.py`)
- **Purpose**: Evidence and source attribution
- **Key Routes**:
  - `/provenance` - Evidence explorer
  - `/provenance/sources` - Source management
  - `/provenance/evidence/{id}` - Evidence detail

### 8. Theory Views (`theory.py`)
- **Purpose**: Speculative theory management
- **Key Routes**:
  - `/theory` - Browse theories
  - `/theory/new` - Create new theory
  - `/theory/{id}` - Theory detail

### 9. Validation Views (`validation.py`)
- **Purpose**: Research validation workflow
- **Key Routes**:
  - `/validation` - Validation dashboard
  - `/validation/artifacts` - Validate artifacts
  - `/validation/verify` - Verification workflow

### 10. Flow Views (`flow.py`)
- **Purpose**: Pipeline state visualization
- **Key Routes**:
  - `/flow` - Pipeline status
  - `/flow/transitions` - State transitions
  - `/flow/abort` - Abort active runs

## HTMX Integration

All views use HTMX for partial page updates:

```python
@app.get("/research/start", response_class=HTMLResponse)
async def start_research_view(state: State = Depends()):
    """Start new research run"""
    return TemplateResponse(
        name="research/start.html",
        context={"run_id": None},
    )
```

## Static Assets

```
backend/app/static/
└── css/
    └── (empty - uses CDN or inline styles)
```

## Templates

```
backend/app/templates/
├── base.html         # Base template with HTMX setup
├── layout.html       # Common layout
└── (dynamic partials generated per view)
```

## Data Flow

```
User → HTMX Request → FastAPI View → Template + Data → HTML Response
                                      ↓
                        HTMX Patch → Update DOM fragment
```

## External Dependencies

- **HTMX** - Client-side DOM manipulation
- **Jinja2** - Server-side templating
- **FastAPI** - HTTP server

## Related Areas

- **Backend Module Map** ([BACKEND.md](BACKEND.md)) - Service layer
- **Database Map** ([DATABASE.md](DATABASE.md)) - Data sources
- **Architecture Map** ([ARCHITECTURE.md](ARCHITECTURE.md)) - System overview

---

*Note: This frontend is server-rendered HTMX, not a separate SPA.*
