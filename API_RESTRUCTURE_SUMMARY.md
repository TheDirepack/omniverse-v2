# API Restructure Summary

## Overview
Complete API restructure from flat `/api/` routes to organized `/api/v1/` with clear domain separation.

## New API Structure

### `/api/v1/db/` - Database Operations
- **`/db/universes`** - Universe CRUD (create, search, delete, etc.)
- **`/db/worlds`** - World operations (alias for universes)
- **`/db/artifacts`** - Artifact CRUD
- **`/db/notebook`** - Notebook operations
- **`/db/claims`** - Knowledge claims and research results
- **`/db/snapshots`** - Snapshot management
- **`/db/registry`** - World registry
- **`/db/reset-health`** - Reset health checks

### `/api/v1/execution/` - Execution & Workflow
- **`/execution/runs/start`** - Start research run
- **`/execution/runs/abort`** - Abort specific run
- **`/execution/runs/abort-all`** - Abort all runs
- **`/execution/runs/active`** - Get active runs
- **`/execution/runs/activity`** - Get agent activity
- **`/execution/runs/reset`** - Reset activity logs
- **`/execution/runs/history`** - Get run history
- **`/execution/runs/{run_id}`** - Run details
- **`/execution/runs/{run_id}/acquisition`** - Acquisition data
- **`/execution/runs/{run_id}/phase`** - Phase details
- **`/execution/runs/{run_id}/logs`** - Run logs
- **`/execution/runs/logs`** - File logs (filterable)
- **`/execution/runs/{run_id}/logs/stream`** - Real-time logs
- **`/execution/tiering/start`** - Start tiering workflow
- **`/execution/extrapolation/start`** - Start extrapolation
- **`/execution/search/start`** - Start focused search

### `/api/v1/settings/` - Configuration
- **`/settings/providers`** - Provider list
- **`/settings/providers/{id}`** - Provider by ID
- **`/settings/providers/{id}/models`** - Provider models
- **`/settings/providers/{id}/sync`** - Sync provider models
- **`/settings/providers/{id}/delete`** - Delete provider
- **`/settings/provider-keys`** - API keys management
- **`/settings/routes`** - Agent routes
- **`/settings/general`** - General settings
- **`/settings/reset-health`** - Reset health checks
- **`/settings/reset-db`** - Reset databases

### `/api/v1/tools/` - Utility Operations
- **`/tools/logs/clear`** - Clear logs
- **`/tools/db/reset`** - Reset database
- **`/tools/registry/search`** - Search registry

## Old API Routes (Deprecated)
All old `/api/` routes have been disabled and will be removed in a future release.

## UI Updates

### Updated Templates
1. **`knowledge.html`** - Updated artifact search to `/api/v1/db/artifacts`
2. **`logs.html`** - Updated run queries to `/api/v1/execution/runs`
3. **`settings.html`** - Updated provider sync to `/api/v1/settings/providers`

### JavaScript Updates
1. **`settings.html`** - Updated `syncModels()` to use new endpoint
2. **`settings.html`** - Updated provider fetch to `/api/v1/settings/providers`
3. **`settings.html`** - Updated provider keys to `/api/v1/settings/providers/keys`

## Benefits
1. **Clear Domain Separation** - DB, Execution, Settings, Tools clearly separated
2. **Versioned API** - `/api/v1/` prefix allows future versions
3. **Consistent Naming** - Resource-oriented paths (`/runs/{id}` not `/run/{id}`)
4. **Better Organization** - Related operations grouped logically
5. **Easier Maintenance** - Clear boundaries between concerns

## Migration Notes
- All old API endpoints are now disabled
- UI has been updated to use new endpoints
- No breaking changes for the user-facing application

## Files Changed
- `backend/app/main.py` - Removed old router imports
- `backend/app/templates/pages/knowledge.html` - Updated API calls
- `backend/app/templates/pages/logs.html` - Updated API calls  
- `backend/app/templates/pages/settings.html` - Updated API calls
- `backend/app/templates/components/artifact_list.html` - Updated API calls
- `backend/app/templates/components/world_list.html` - Updated API calls
- `backend/app/api/v1/` - Created new API structure

