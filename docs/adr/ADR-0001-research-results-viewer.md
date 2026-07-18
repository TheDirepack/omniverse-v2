# ADR-0001: Research Results Viewer Implementation

## Status
**Accepted**

## Context

Users need a dedicated page to view detailed results from completed research runs. Currently, research runs create artifacts in the background without providing an easy way for users to:
1. See what was discovered during a specific run
2. Review evidence sources
3. Navigate between related knowledge
4. Manage old/failed research runs

The existing `/research` page shows queue status but doesn't provide detail views of individual runs.

## Decision

Create a new Research Results Viewer feature at `/research/results/{run_id}` with:

### API Endpoints
- `GET /api/v1/execution/results/{run_id}` - Fetch run state and artifacts
- `POST /api/v1/execution/results/{run_id}/delete` - Delete execution logs

### UI Page
- HTMX-based page displaying:
  - Run metadata (status, timestamps, target worlds)
  - Execution timeline (agent nodes, thoughts, token usage)
  - Artifacts created with confidence levels
  - Evidence sections with source links
  - Actions: View in Knowledge Graph, Delete Run

### Technical Approach
- Use FastAPI with HTMLResponse for seamless HTMX integration
- Query Main DB for Artifacts and Evidence
- Parse execution state_snapshot JSON to correlate artifacts
- Support both completed and in-progress runs

## Consequences

### Positive
- Users can review research outcomes before submission
- Better visibility into AI agent reasoning (thoughts, tokens)
- Evidence provenance clearly shown
- Ability to delete failed runs without losing artifacts

### Negative
- Additional database queries for artifact/artifact_relation lookups
- New template file increases frontend complexity slightly
- Requires run_id tracking (already implemented via ExecutionService)

### Neutral
- No breaking changes to existing APIs
- Backward compatible with old research runs

## Alternatives Considered

### Alternative 1: Modals within Research Page
**Pros:** Single page, no navigation
**Cons:** Cluttered UI, limited space for details
**Rejected:** Modal approach would be too cramped for evidence sections

### Alternative 2: REST API only with custom frontend
**Pros:** Decoupled, flexible
**Cons:** Extra HTTP round trip, less seamless HTMX experience
**Rejected:** HTMX native approach provides better UX

### Alternative 3: Expand existing research page
**Pros:** No new pages
**Cons:** Existing page already complex, would require major refactor
**Rejected:** Separate page is cleaner architecture

## Implementation Date
July 17, 2026

## Related
- ADR-0002: World Directory Transformation (Upcoming)
- Fix #10: Research Results Viewer (IMPLEMENTATION_SPEC.md)
