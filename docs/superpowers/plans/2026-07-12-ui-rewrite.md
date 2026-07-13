# Implementation Plan: Project C - The Knowledge Hub

## Goal
Implement a "World-Scoped" Knowledge Hub with a high-density sidebar-driven layout for exploring artifacts.

## Phase 1: Backend Implementation

### Task C1: Backend Repository
- **Files**: `backend/app/repositories/artifact.py`
- **Logic**: Implement `ArtifactRepository` to query `Artifact`, `ArtifactRelation`, and `Evidence` models. Include methods: `get_by_universe(universe_id: int, limit: int, offset: int)`, `search_artifacts(universe_id: int, query: str, limit: int, offset: int)`, and `get_artifact_with_details(artifact_id: int)`.
- **Test Command**: `pytest backend/tests/backend/test_artifact_repository.py`
- **Expected Outcome**: Pass if repository methods correctly fetch and filter data from the database.

### Task C2: Backend Service
- **Files**: `backend/app/services/artifact_service.py`
- **Logic**: Implement `ArtifactService` to orchestrate `ArtifactRepository` and `UniverseService`. Include methods: `list_artifacts(universe_id: int, search_query: str | None, filter_params: dict | None)` and `get_artifact_details(artifact_id: int)`.
- **Test Command**: `pytest backend/tests/backend/test_artifact_service.py`
- **Expected Outcome**: Pass if service correctly handles business logic and returns structured data.

### Task C3: Backend Router
- **Files**: `backend/app/api/routers/artifacts.py`, `backend/app/api/main.py`
- **Logic**: Define `artifacts_router` with `GET /` (list) and `GET /{artifact_id}` (detail) endpoints. Register `artifacts_router` in `backend/app/api/main.py`.
- **Test Command**: `pytest backend/tests/backend/test_artifact_router.py`
- **Expected Outcome**: Pass if API endpoints return the expected JSON responses.

## Phase 2: Frontend Implementation

### Task C4: Knowledge Hub View & Top Bar
- **Files**: `backend/app/views/knowledge_hub.py`, `backend/app/views/components/knowledge_top_bar.py`
- **Logic**: Create `knowledge_hub` main view with a split-pane layout. Implement `knowledge_top_bar` containing a World Selector dropdown, Search input, Filter button, Apply button, and "🚀 Focused Research" button.
- **Test Command**: `pytest backend/tests/ui/test_knowledge_hub.py`
- **Expected Outcome**: Pass if the hub layout renders and the top bar triggers appropriate HTMX requests.

### Task C5: Artifact List & Inspector
- **Files**: `backend/app/views/components/artifact_list.py`, `backend/app/views/components/artifact_inspector.py`
- **Logic**: Implement `artifact_list` (left panel) with high-density rows and hover-based previews. Implement `artifact_inspector` (right panel) to display full artifact descriptions, evidence/provenance with confidence, and related artifacts.
- **Test Command**: `pytest backend/tests/ui/test_artifact_components.py`
- **Expected Outcome**: Pass if the list and inspector render correctly and facilitate interactive exploration.
