# API Documentation

**Last Updated:** 2026-07-21

## Overview

Omniverse V2 provides a REST API organized under the `/api/v1/` prefix, plus HTMX view routes for the settings/settings UI. The UI uses both the REST API (for data queries) and view routes (for form submissions and page rendering).

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints are publicly accessible. No authentication is required.

## Table of Contents

- [REST API (`/api/v1/`)](#rest-api-apiv1)
- [HTMX View Routes](#htmx-view-routes)
- [Old API Routes (Deprecated)](#old-api-routes-deprecated)
- [Endpoint Mappings](#endpoint-mappings)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)

---

## REST API (`/api/v1/`)

### `/api/v1/db/` - Database Operations

#### `/db/worlds`

Universe CRUD operations.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/db/worlds` | GET | List universes (JSON) |
| `/db/worlds` | POST | Create universe |
| `/db/worlds/by-uuid/{uuid}` | GET | Get universe by UUID |
| `/db/worlds/{id}` | GET | Get universe by ID or slug |
| `/db/worlds/{id}` | PUT | Update universe |
| `/db/worlds/{id}` | DELETE | Delete universe |
| `/db/worlds/{world_id}/reset-explored` | POST | Reset explored flag |
| `/db/worlds/reset-all-explored` | POST | Reset all explored flags |
| `/db/worlds/clear-logs` | POST | Clear execution logs |
| `/db/worlds/reset-database` | POST | Full database reset |

#### `/db/artifacts`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/db/artifacts` | GET | List artifacts (JSON, paginated) |
| `/db/artifacts/list` | GET | List artifacts (HTML) |
| `/db/artifacts/search` | GET | Search artifacts (HTML) |
| `/db/artifacts/{artifact_id}` | GET | Get artifact details (HTML) |
| `/db/artifacts/save` | POST | Save a single artifact |

#### `/db/notebook`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/db/notebook/entries` | POST | Save notebook entries (batch) |
| `/db/notebook/entries/{entry_id}` | DELETE | Delete notebook entry |
| `/db/notebook/entries/{entry_id}` | PUT | Update notebook entry |

#### `/db/claims`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/db/claims/claims` | GET | Get knowledge claims |
| `/db/claims/claims/notebook` | GET | Get notebook claims |
| `/db/claims/results` | GET | Get research results |
| `/db/claims/results/tiers` | GET | Get tier results |
| `/db/claims/theories` | GET | Get speculative theories |

**Example: Get Research Results**

```bash
curl "http://localhost:8000/api/v1/db/claims/results"
```

Response:
```json
{
  "tier_system": "Tier 1-10 Scale",
  "worlds": [
    {
      "id": 1,
      "name": "Marvel Comics",
      "summary": "Major superhero franchise",
      "is_explored": true,
      "tier": 8,
      "tier_justification": "High-powered entities",
      "theory": "Speculative theory text",
      "theory_audit": "Audit feedback"
    }
  ],
  "anomalies": [
    {
      "world_id": 1,
      "description": "Inconsistent power levels",
      "detected_at": "2026-07-16T12:00:00Z"
    }
  ]
}
```

---

### `/api/v1/execution/` - Execution & Workflow

#### `/execution/runs`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/execution/runs/start` | POST | Start research workflow (form/JSON) |
| `/execution/runs/workflow` | POST | Start research workflow (JSON) |
| `/execution/runs/tiering` | POST | Start tiering workflow |
| `/execution/runs/extrapolate` | POST | Start extrapolation |
| `/execution/runs/focused-search` | POST | Start focused search |
| `/execution/runs/abort` | POST | Abort specific run |
| `/execution/runs/abort-all` | POST | Abort all runs |
| `/execution/runs/active-detailed` | GET | Get active runs (HTML) |
| `/execution/runs/agent-activity` | GET | Get agent activity |
| `/execution/runs/reset-activity` | POST | Reset activity logs |
| `/execution/runs/history` | GET | Get run history (HTML) |
| `/execution/runs/{run_id}` | GET | Run details (HTML) |
| `/execution/runs/{run_id}/acquisition` | GET | Acquisition artifacts (HTML) |
| `/execution/runs/{run_id}/phase-details` | GET | Phase details (HTML) |
| `/execution/runs/logs/file` | GET | File logs with filtering |
| `/execution/runs/logs/{run_id}` | GET | Real-time logs (SSE stream) |
| `/execution/runs/claims` | DELETE | Delete all claims |

**Example: Start Research Workflow**

```bash
curl -X POST "http://localhost:8000/api/v1/execution/runs/workflow" \
  -H "Content-Type: application/json" \
  -d '{
    "universe_uuids": ["uuid-123", "uuid-456"]
  }'
```

Response:
```json
{
  "status": "started",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "uuids": ["uuid-123", "uuid-456"]
}
```

**Example: Get Real-time Logs**

```bash
curl -N "http://localhost:8000/api/v1/execution/runs/logs/{run_id}"
```

Response (SSE):
```
data: {"id": 1, "node_name": "Manager", "thought": "Starting research...", "status": "RESEARCH", "created_at": "2026-07-16T12:00:00Z"}

data: {"id": 2, "node_name": "Researcher", "thought": "Searching web...", "status": "RESEARCH", "created_at": "2026-07-16T12:00:01Z"}

data: {"finished": true}
```

---

### `/api/v1/settings/` - Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/settings/general` | GET | List settings |
| `/settings/general` | POST | Update a setting |
| `/settings/general/reset-health` | POST | Reset candidate health |
| `/settings/providers` | GET | List providers |
| `/settings/providers` | POST | Upsert provider |
| `/settings/providers/{id}/models` | GET | Get provider models |
| `/settings/providers/keys` | POST | Upsert API key |
| `/settings/providers/keys/{id}` | DELETE | Delete API key |
| `/settings/providers/{id}` | DELETE | Delete provider |
| `/settings/routes` | GET | List agent routes |
| `/settings/routes` | POST | Create agent route |
| `/settings/routes/model-status` | GET | Model init status |
| `/settings/routes/{task_type}` | GET | Get route by task type |
| `/settings/routes/{task_type}` | POST | Configure agent route |

**Example: List Providers**

```bash
curl "http://localhost:8000/api/v1/settings/providers"
```

Response:
```json
[
  {
    "id": 1,
    "name": "OpenRouter",
    "provider_type": "openrouter",
    "base_url": "https://openrouter.ai/api/v1",
    "models": ["gpt-4o", "claude-3-5-sonnet"]
  }
]
```

---

### `/api/v1/tools/` - Utility Operations

#### `/tools/worlds`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tools/worlds` | GET | List worlds (JSON, paginated) |
| `/tools/worlds` | POST | Add/create world |
| `/tools/worlds/search` | GET | Search worlds |
| `/tools/worlds/registry` | GET | List registry with search |
| `/tools/worlds/by-uuid/{uuid}` | GET | Get world by UUID |
| `/tools/worlds/{world_id}/reset-explored` | POST | Reset explored |
| `/tools/worlds/reset-all-explored` | POST | Reset all explored |
| `/tools/worlds/research-unexplored` | POST | Research unexplored worlds |
| `/tools/worlds/import` | POST | Import from registry |
| `/tools/worlds/create` | POST | Create universe |
| `/tools/worlds/{world_id}` | DELETE | Delete world |
| `/tools/worlds/reset-database` | POST | Reset database |
| `/tools/worlds/clear-logs` | POST | Clear logs |
| `/tools/worlds/search-duplicates` | GET | Find duplicates |
| `/tools/worlds/merge` | POST | Merge worlds |
| `/tools/worlds/snapshots` | POST | Create snapshot |
| `/tools/worlds/snapshots` | GET | List snapshots |
| `/tools/worlds/snapshots/{id}` | DELETE | Delete snapshot |

**Example: List Worlds**

```bash
curl "http://localhost:8000/api/v1/tools/worlds?limit=10&offset=0"
```

Response:
```json
{
  "items": [
    {
      "id": 1,
      "uuid": "uuid-123",
      "slug": "marvel-comics",
      "name": "Marvel Comics",
      "summary": "Major superhero franchise",
      "is_explored": true
    }
  ],
  "total": 150,
  "limit": 10,
  "offset": 0
}
```

---

## HTMX View Routes

The settings UI uses HTMX view routes (not the REST API) for form submissions and page rendering. These routes return HTML fragments.

### Settings View Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/settings/tab/general` | GET | General settings tab |
| `/settings/tab/providers` | GET | Provider management tab |
| `/settings/tab/routes` | GET | Agent routing tab |
| `/settings/tab/health` | GET | Health monitoring tab |
| `/settings/providers/upsert` | POST | Create/update provider |
| `/settings/providers/{id}` | GET | Get provider edit form |
| `/settings/providers/new` | GET | Get new provider form |
| `/settings/providers/{id}/delete` | POST | Delete provider |
| `/settings/providers/{id}/keys` | POST | Add API key |
| `/settings/providers/{id}/sync` | POST | Sync provider models |
| `/settings/routes/upsert` | POST | Create/update route |
| `/settings/routes/{id}` | GET | Get route edit form |
| `/settings/routes/{id}/delete` | POST | Delete route |
| `/settings/general/update` | POST | Update a setting |
| `/settings/general/delete/{key}` | POST | Delete a setting |
| `/settings/reset-health` | POST | Reset circuit breakers |
| `/settings/snapshots` | GET | List snapshots (HTML) |
| `/settings/snapshots/create` | POST | Create snapshot |
| `/settings/snapshots/{id}` | DELETE | Delete snapshot |
| `/settings/snapshots/{id}/restore` | POST | Restore snapshot |

### Worlds View Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/worlds` | GET | Universe list page |
| `/worlds/{uuid}/details` | GET | World details page |
| `/worlds/{uuid}/neighborhood` | GET | Universe neighborhood |
| `/worlds/create` | POST | Create universe |
| `/worlds/{id}/delete` | POST | Delete universe |

---

## Old API Routes (Deprecated)

The following API routes were used in previous versions and are now **commented out** in `main.py`. They have been replaced by the `/api/v1/` structure and HTMX view routes.

### Deprecated Endpoints

| Old Endpoint | Replacement | Status |
|--------------|-------------|--------|
| `/api/research/start` | `/api/v1/execution/runs/workflow` | Commented out |
| `/api/runs` | `/api/v1/execution/runs` | Commented out |
| `/api/settings` | `/settings/tab/*` (HTMX views) | Commented out |
| `/api/providers` | `/settings/providers/*` (HTMX views) | Commented out |
| `/api/artifacts` | `/api/v1/db/artifacts` | Commented out |
| `/api/notebook` | `/api/v1/db/notebook` | Commented out |
| `/api/worlds` | `/api/v1/tools/worlds` | Commented out |

**Current status**: All old API endpoints are commented out in `backend/app/main.py:129-136`.

## Endpoint Mappings

### DB Operations

| Old Route | New Route |
|-----------|-----------|
| `/api/artifacts` | `/api/v1/db/artifacts` |
| `/api/artifacts/{id}` | `/api/v1/db/artifacts/{artifact_id}` |
| `/api/artifacts/search` | `/api/v1/db/artifacts/search` |

### Execution

| Old Route | New Route |
|-----------|-----------|
| `/api/runs` | `/api/v1/execution/runs` |
| `/api/runs/{id}/abort` | `/api/v1/execution/runs/abort` |
| `/api/runs/{id}/logs` | `/api/v1/execution/runs/logs/{run_id}` |
| `/api/runs/active` | `/api/v1/execution/runs/active-detailed` |

### Settings

| Old Route | New Route |
|-----------|-----------|
| `/api/settings` | `/settings/tab/general` (HTMX) or `/api/v1/settings/providers` |
| `/api/settings/providers` | `/settings/tab/providers` (HTMX) or `/api/v1/settings/providers` |
| `/api/settings/providers/{id}/models` | `/api/v1/settings/providers/{id}/models` |
| `/api/settings/providers/{id}/sync` | `/settings/providers/{id}/sync` (HTMX) |
| `/api/settings/providers/{id}/keys` | `/settings/providers/{id}/keys` (HTMX) |

### Tools

| Old Route | New Route |
|-----------|-----------|
| `/api/worlds` | `/api/v1/tools/worlds` |
| `/api/worlds/{id}` | `/api/v1/tools/worlds/{world_id}` |
| `/api/worlds/search` | `/api/v1/tools/worlds/search` |

---

## Usage Examples

### Complete Research Workflow

```bash
# 1. Add a new universe
curl -X POST "http://localhost:8000/api/v1/tools/worlds" \
  -H "Content-Type: application/json" \
  -d '{"world_name": "Marvel Comics", "auto_research": true}'

# 2. Check active runs
curl "http://localhost:8000/api/v1/execution/runs/active-detailed"

# 3. Get real-time logs
curl -N "http://localhost:8000/api/v1/execution/runs/logs/{run_id}"

# 4. Get research results
curl "http://localhost:8000/api/v1/db/claims/results"
```

### Search and Query

```bash
# Search for artifacts
curl "http://localhost:8000/api/v1/db/artifacts/search?q=superhero&universe_id=1"

# List all artifacts with pagination
curl "http://localhost:8000/api/v1/db/artifacts?limit=50&offset=0"

# Get specific artifact details
curl "http://localhost:8000/api/v1/db/artifacts/123"
```

### World Management

```bash
# List all worlds
curl "http://localhost:8000/api/v1/tools/worlds"

# Search worlds
curl "http://localhost:8000/api/v1/tools/worlds/search?q=marvel&explored=true"

# Get world by UUID
curl "http://localhost:8000/api/v1/tools/worlds/by-uuid/{uuid}"

# Research all unexplored worlds
curl -X POST "http://localhost:8000/api/v1/tools/worlds/research-unexplored"
```

---

## Error Handling

All API endpoints follow standard HTTP status codes:

| Status Code | Meaning |
|-------------|---------|
| `200` | Success |
| `201` | Created |
| `400` | Bad Request |
| `404` | Not Found |
| `422` | Validation Error |
| `500` | Server Error |

### Error Response Format

```json
{
  "detail": "Error message describing the issue"
}
```

### Common Errors

- **400 Bad Request**: Invalid request format or missing required fields
- **404 Not Found**: Resource not found
- **422 Validation Error**: Data validation failure (e.g., mismatched form data)

---

## Additional Resources

- **Architecture**: See `docs/CODEMAPS/ARCHITECTURE.md`
- **Backend Structure**: See `docs/CODEMAPS/BACKEND.md`
- **Database Schema**: See `docs/CODEMAPS/DATABASE.md`
- **Frontend**: See `docs/CODEMAPS/FRONTEND.md`

---

*Last Updated: 2026-07-21*
