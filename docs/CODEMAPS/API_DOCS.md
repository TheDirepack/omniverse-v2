# API Documentation

**Last Updated:** 2026-07-16

## Overview

Omniverse V2 provides a comprehensive REST API for interacting with the multi-agent power-tiering platform. All API endpoints are organized under the `/api/v1/` prefix for versioned API support.

## Base URL

```
http://localhost:8000/api/v1/
```

## Authentication

All API endpoints are publicly accessible. No authentication is required.

## Table of Contents

- [New API Structure](#new-api-structure)
- [Old API Routes (Deprecated)](#old-api-routes-deprecated)
- [Endpoint Mappings](#endpoint-mappings)
- [Usage Examples](#usage-examples)
- [Error Handling](#error-handling)

---

## New API Structure

### `/api/v1/db/` - Database Operations

Endpoints for database CRUD operations, artifact management, and knowledge graph queries.

#### `/db/artifacts`

Artifact CRUD operations.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/db/artifacts` | GET | List artifacts (JSON) |
| `/db/artifacts/list` | GET | List artifacts (HTML) |
| `/db/artifacts/search` | GET | Search artifacts (HTML) |
| `/db/artifacts/{artifact_id}` | GET | Get artifact details (HTML) |

**Example: List Artifacts**

```bash
curl "http://localhost:8000/api/v1/db/artifacts?limit=10&offset=0"
```

Response:
```json
[
  {
    "id": 1,
    "name": "Example Entity",
    "type": "Entity",
    "universe_id": 1,
    "description": "An example entity"
  }
]
```

#### `/db/notebook`

Notebook save/update/delete operations for research workspace.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/db/notebook/entries` | POST | Save notebook entries |
| `/db/notebook/entries/{entry_id}` | DELETE | Delete notebook entry |

**Example: Save Notebook Entries**

```bash
curl -X POST "http://localhost:8000/api/v1/db/notebook/entries" \
  -H "Content-Type: application/json" \
  -d '{
    "universe_name": "Marvel Comics",
    "items": [
      {
        "title": "Character Power Assessment",
        "summary": "Evaluated power levels",
        "details": "Full analysis...",
        "kind": "Observation",
        "priority": 1
      }
    ]
  }'
```

Response:
```json
{
  "status": "success",
  "results": [
    {"status": "saved", "entry_id": 123}
  ]
}
```

#### `/db/claims`

Knowledge claims and research results.

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

Endpoints for managing research runs, execution state, and agent activities.

#### `/execution/runs`

Research run management.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/execution/runs/workflow` | POST | Start research workflow |
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
| `/execution/runs/{run_id}/acquisition` | GET | Acquisition data (HTML) |
| `/execution/runs/{run_id}/phase-details` | GET | Phase details (HTML) |
| `/execution/runs/logs/file` | GET | File logs |
| `/execution/runs/logs/{run_id}` | GET | Real-time logs (stream) |

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

**Example: Get Active Runs**

```bash
curl "http://localhost:8000/api/v1/execution/runs/active-detailed"
```

Response:
```html
<!-- HTML table with run details -->
<table>
  <tr>
    <td>550e8400-e29b-41d4-a716-446655440000</td>
    <td>Marvel Comics</td>
    <td>General Research</td>
    <td>30</td>
    <td>RESEARCH</td>
  </tr>
</table>
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

Endpoints for system configuration, LLM providers, and settings management.

#### `/settings/providers`

LLM provider management.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/settings/providers` | GET | List providers |
| `/settings/providers` | POST | Upsert provider |
| `/settings/providers/{provider_id}` | GET | Get provider by ID |
| `/settings/providers/{provider_id}/models` | GET | Get provider models |
| `/settings/providers/{provider_id}/sync` | POST | Sync provider models |
| `/settings/providers/{provider_id}/keys` | POST | Upsert API keys |
| `/settings/providers/{provider_id}/keys/{key_id}` | DELETE | Delete API key |
| `/settings/providers/{provider_id}` | DELETE | Delete provider |

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

**Example: Sync Provider Models**

```bash
curl -X POST "http://localhost:8000/api/v1/settings/providers/{provider_id}/sync"
```

Response:
```json
{
  "models": [
    {
      "id": "gpt-4o",
      "name": "GPT-4o",
      "description": "Latest GPT-4o model"
    },
    {
      "id": "claude-3-5-sonnet",
      "name": "Claude 3.5 Sonnet",
      "description": "Anthropic's latest model"
    }
  ]
}
```

**Example: Upsert API Key**

```bash
curl -X POST "http://localhost:8000/api/v1/settings/providers/{provider_id}/keys" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": 1,
    "api_key": "sk-abc123",
    "priority": 1
  }'
```

Response:
```json
{
  "status": "success",
  "key_id": 42
}
```

---

### `/api/v1/tools/` - Utility Operations

Endpoints for utility operations, world management, and system tools.

#### `/tools/worlds`

World/universe management.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tools/worlds` | GET | List worlds (JSON) |
| `/tools/worlds` | POST | Add world |
| `/tools/worlds/search` | GET | Search worlds |
| `/tools/worlds/registry` | GET | List registry |
| `/tools/worlds/by-uuid/{uuid}` | GET | Get world by UUID |
| `/tools/worlds/{world_id}/reset-explored` | POST | Reset explored status |
| `/tools/worlds/reset-all-explored` | POST | Reset all explored |
| `/tools/worlds/research-unexplored` | POST | Research unexplored worlds |
| `/tools/worlds/import` | POST | Import from registry |
| `/tools/worlds/create` | POST | Create universe |
| `/tools/worlds/{world_id}` | DELETE | Delete world |
| `/tools/worlds/reset-database` | POST | Reset database |
| `/tools/worlds/clear-logs` | POST | Clear logs |

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

**Example: Add World**

```bash
curl -X POST "http://localhost:8000/api/v1/tools/worlds" \
  -H "Content-Type: application/json" \
  -d '{
    "world_name": "DC Comics",
    "franchise": "DC",
    "auto_research": true
  }'
```

Response:
```json
{
  "status": "queued",
  "run_id": "550e8400-e29b-41d4-a716-446655440001",
  "world_name": "DC Comics"
}
```

**Example: Search Registry**

```bash
curl "http://localhost:8000/api/v1/tools/worlds/registry?q=dc"
```

Response:
```json
{
  "worlds": [
    {
      "id": "dc-comics",
      "name": "DC Comics",
      "description": "DC superhero universe"
    }
  ]
}
```

---

## Old API Routes (Deprecated)

The following API routes were used in previous versions and are now deprecated. They have been replaced by the new `/api/v1/` structure.

### Deprecated Endpoints

| Old Endpoint | New Equivalent | Status |
|--------------|----------------|--------|
| `/api/research/start` | `/api/v1/execution/runs/workflow` | ❌ Deprecated |
| `/api/runs` | `/api/v1/execution/runs` | ❌ Deprecated |
| `/api/settings` | `/api/v1/settings/providers` | ❌ Deprecated |
| `/api/providers` | `/api/v1/settings/providers` | ❌ Deprecated |
| `/api/artifacts` | `/api/v1/db/artifacts` | ❌ Deprecated |
| `/api/notebook` | `/api/v1/db/notebook` | ❌ Deprecated |
| `/api/worlds` | `/api/v1/tools/worlds` | ❌ Deprecated |

### Removal Timeline

- **Current Version (2.0.0)**: Old endpoints are disabled but still functional
- **Future Release**: Old endpoints will be completely removed

## Endpoint Mappings

Complete mapping of old endpoints to new ones:

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
| `/api/settings` | `/api/v1/settings/providers` |
| `/api/settings/providers` | `/api/v1/settings/providers` |
| `/api/settings/providers/{id}/models` | `/api/v1/settings/providers/{id}/models` |
| `/api/settings/providers/{id}/sync` | `/api/v1/settings/providers/{id}/sync` |
| `/api/settings/providers/{id}/keys` | `/api/v1/settings/providers/{id}/keys` |

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

# 5. Get tier assignments
curl "http://localhost:8000/api/v1/db/claims/results/tiers"
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

# Reset explored status for a world
curl -X POST "http://localhost:8000/api/v1/tools/worlds/{world_id}/reset-explored"

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
- **422 Validation Error**: Data validation failure

---

## Additional Resources

- **Architecture**: See `docs/CODEMAPS/ARCHITECTURE.md`
- **Backend Structure**: See `docs/CODEMAPS/BACKEND.md`
- **Database Schema**: See `docs/CODEMAPS/DATABASE.md`
- **Frontend**: See `docs/CODEMAPS/FRONTEND.md`

---

*Last Updated: 2026-07-16*
