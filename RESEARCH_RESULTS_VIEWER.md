# Research Results Viewer - Implementation Documentation

## Overview

The Research Results Viewer provides a comprehensive interface for viewing and managing research runs in Omniverse V2. It displays run metadata, execution timeline, artifacts created during research, and associated evidence sources.

## Features

### 1. Run Metadata Display
- **Run ID**: Unique identifier for the research run
- **Target Worlds**: List of universes being researched
- **Timestamps**: Start and completion times
- **Status**: Current state (in_progress, completed, failed, etc.)
- **Active Task**: Current agent/node performing work

### 2. Execution Timeline
Chronological display of all agent nodes executed during the run:
- Node name (Researcher, DB Architect, etc.)
- Timestamp for each step
- Thought/processing details
- Duration and token usage
- Status indicators (COMPLETED, FAILED, IN_PROGRESS)

### 3. Artifacts Created
Detailed listing of knowledge artifacts generated:
- **Artifact Properties**: Name, type, confidence, freshness
- **Universe Context**: Which universe the artifact belongs to
- **Evidence Sources**: Links to original web sources with sections referenced
- **Payload Details**: Raw JSON data for deep inspection
- **Support Metrics**: Evidence count and verification status

### 4. Actions
- **View in Knowledge Graph**: Navigate to the artifact in `/knowledge` view
- **Delete Run**: Remove execution logs (artifacts preserved)

## Architecture

### Backend Components

#### `backend/app/views/research_results.py`
Main view router with two endpoints:

**GET /research/results/{run_id}**
- Fetches execution states from `ExecutionState` table
- Queries `Artifact` table for related artifacts
- Joins with `Evidence` table for source information
- Returns structured data with run metadata, artifacts, and evidence

**POST /research/results/{run_id}/delete**
- Clears execution logs via `ExecutionRepository.clear_logs_for_run()`
- Preserves artifacts in Knowledge Graph
- Returns success confirmation

#### Database Tables Used
1. **ExecutionState**: Stores per-node execution history
   - `run_id`, `node_name`, `thought`, `status`, `state_snapshot`, `created_at`

2. **Artifact**: Knowledge graph entities
   - `id`, `universe_id`, `type`, `name`, `confidence`, `evidence_refs`, `payload_json`

3. **Evidence**: Source documentation
   - `id`, `universe_id`, `source_url`, `section`, `artifact_id`

4. **Universe**: Target worlds being researched
   - `id`, `uuid`, `name`, `parent_id`

### Frontend Components

#### Template: `backend/app/templates/pages/research_results.html`
HTMX-based template with:
- Toolbar with navigation and delete button
- Status banner with color-coded indicators
- Metadata grid showing key statistics
- Execution timeline with collapsible steps
- Artifact cards with:
  - Header row with properties
  - Universe and confidence badges
  - Description preview
  - "View in Knowledge" link
  - Evidence section with source links
  - Payload detail modal trigger

#### JavaScript Features
- Delete confirmation dialog
- Toast notifications for success/error states
- Payload modal for detailed JSON inspection
- Responsive layout with Tailwind CSS

## Data Flow

```mermaid
graph TD
    A[User clicks Results URL] --> B{Run exists?}
    B -->|No| C[404 Error]
    B -->|Yes| D[GET /research/results/{run_id}]
    D --> E[Fetch ExecutionStates]
    E --> F[Parse state_snapshots]
    F --> G[Extract universe/artifact IDs]
    G --> H[Query Artifacts table]
    H --> I[Query Evidence table]
    I --> J[Join with Universe names]
    J --> K[Return structured data]
    K --> L[Render HTML template]
    
    M[Delete Request] --> N[POST /research/results/{run_id}/delete]
    N --> O[Clear ExecutionStates]
    O --> P[Return success]
```

## HTMX Integration

The view uses HTMX for seamless UX:

1. **Navigation**: Standard anchor tags with href attributes
2. **Delete Action**: Form POST with confirmation via JavaScript
3. **Dynamic Content**: No HTMX triggers needed - entire page renders

## Usage Examples

### View Research Results
```
http://localhost:8000/research/results/{run_id}
```

Where `{run_id}` is a UUID like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`.

### Delete a Run
```
<form action="/research/results/{run_id}/delete" method="POST">
  <input type="hidden" name="world_names" value="">
  <button type="submit">Delete</button>
</form>
```

## Implementation Details

### Artifact Matching Strategy
Since the `Artifact` table doesn't have a `run_id` column, artifacts are matched using:
1. Parsing `state_snapshot` JSON from `ExecutionState` for `artifact_id` references
2. Filtering by `universe_id` from research target worlds
3. Combining both methods to ensure all relevant artifacts are displayed

### Evidence Linking
Evidence is retrieved by:
1. Parsing `evidence_refs` from artifact (JSON array of evidence IDs)
2. Querying `Evidence` table where `artifact_id` matches
3. Displaying source URLs and section references

### Status Mapping
Run phases map to display statuses:
- `FINISHED` → completed
- `RESEARCHING` → in_progress
- `DB_INTEGRATION` → integrating
- `SUMMARY` → summarizing
- `FAILED` → failed
- `QUEUED` → queued

## Testing Checklist

- [x] Page loads correctly for valid run_id
- [x] Shows artifacts from run (via state_snapshot parsing)
- [x] Shows evidence sections for each artifact
- [x] "View in Knowledge" links work (href to `/knowledge?artifact={id}`)
- [x] Delete endpoint clears logs without deleting artifacts
- [x] Handles empty runs gracefully (no artifacts message)
- [x] Handles missing runs (404 error)
- [x] Displays execution timeline correctly
- [x] Status badges color-coded properly
- [x] Responsive layout on mobile
- [x] Dark mode support

## Files Created/Modified

### Created
1. `backend/app/views/research_results.py` - Main view router
2. `backend/app/templates/pages/research_results.html` - Enhanced HTMX template

### Modified
1. `backend/app/main.py` - Added research_results_router import and inclusion

## Dependencies

- FastAPI (HTMLResponse, Form, Depends, HTTPException)
- SQLAlchemy/SQLModel (Session, select, delete)
- ExecutionService (repo property)
- RunPhase enum
- Universe, Artifact, Evidence models

## Future Enhancements

1. **Pagination**: For runs with many artifacts
2. **Filtering**: Filter artifacts by type, confidence, universe
3. **Bulk Actions**: Select multiple artifacts for batch operations
4. **Export**: Export artifacts as CSV/JSON
5. **Comparison View**: Side-by-side artifact comparison across runs
6. **Timeline Visualization**: Graphical timeline instead of text list
7. **Artifact Preview**: Inline preview of payload content

## Security Considerations

- Run IDs are validated as strings (UUIDs)
- DELETE endpoint requires confirmation before execution
- Artifacts preserved to maintain Knowledge Graph integrity
- No direct database modifications except log cleanup

## Performance Notes

- Uses indexed queries on `run_id`, `universe_id`, and `artifact_id`
- Evidence fetching uses IN clause for batch retrieval
- State snapshots parsed once per run
- Lazy loading of payload details via modal
