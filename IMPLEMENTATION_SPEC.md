# Omniverse V2 - Implementation Specification

**Date:** July 17, 2026  
**Status:** Planning Phase (READ-ONLY)  
**Approach:** Transform `/worlds` to World Directory with search/filter

---

## 🎯 OVERVIEW

This specification details how to fix the 12 verified issues in Omniverse V2, prioritizing backend stability while building new features.

### Decision Summary
- ✅ **Q1:** Transform `/worlds` to "World Directory" with search/filter
- ✅ **Q2:** Full implementation spec with code examples
- ✅ **Q3:** Parallel tracks (backend + UX simultaneously)
- ✅ **Q4:** No deadline constraint

---

## 🔴 TRACK 1: BACKEND STABILITY

### Fix #1: Unbounded Queries

**Problem:** Multiple endpoints use `limit=5000` without pagination enforcement.

**Files to Modify:**
- `backend/app/views/knowledge.py` (lines 70, 87)
- `backend/app/views/worlds.py` (lines 31, 48, 57, 65, 76, 89, 131, 150, 271)

**Implementation:**
```python
# In database_worlds endpoint (worlds.py line 24-32)
@app.get("/database-worlds", response_class=HTMLResponse)
async def database_worlds(
    request: Request,
    q: str = Query(default=""),
    explored: str = Query(default=""),
    franchise: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
):
    offset = (page - 1) * per_page
    uni_service = UniverseService()
    
    worlds = uni_service.filter_universes(
        q=q, 
        explored=explored, 
        franchise=franchise, 
        limit=per_page,
        offset=offset
    )
    
    total = uni_service.count_universes(q=q, explored=explored, franchise=franchise)
    
    return render_worlds_table(
        request, 
        worlds, 
        q=q, 
        explored=explored, 
        franchise=franchise,
        page=page,
        per_page=per_page,
        total=total
    )
```

**Template Update:** Add pagination controls to `database_worlds.html`:
```html
<div class="flex justify-between items-center mt-4">
    <span>Showing {{ (page-1)*per_page+1 }}-{{ min((page*per_page), total) }} of {{ total }} results</span>
    {% if page > 1 %}
        <a href="?page={{ page-1 }}" class="px-3 py-1 bg-gray-200 rounded">« Prev</a>
    {% endif %}
    <span>{{ page }} / {{ (total + per_page - 1) // per_page }}</span>
    {% if page * per_page < total %}
        <a href="?page={{ page+1 }}" class="px-3 py-1 bg-gray-200 rounded">Next »</a>
    {% endif %}
</div>
```

---

### Fix #2: Silent Failures in Background Tasks

**Problem:** Research tasks fail without user notification.

**File:** `backend/app/views/worlds.py` (batch_research endpoint)

**Implementation:**
```python
@app.post("/batch-research", response_class=HTMLResponse)
async def batch_research(
    request: Request,
    background_tasks: BackgroundTasks,
    world_names: str = Form(...),
):
    import uuid
    from fastapi import HTTPException
    
    names = [w.strip() for w in world_names.split(",") if w.strip()]
    
    if not names:
        raise HTTPException(status_code=400, detail="No worlds selected")
    
    # Start research tasks
    run_ids = []
    for name in names:
        run_id = str(uuid.uuid4())
        background_tasks.add_task(run_pipeline_in_background, run_id, [name])
        run_ids.append({"run_id": run_id, "world": name})
    
    # Return success with run IDs
    return render_worlds_table(
        request, 
        [], 
        batch_started=len(names),
        run_ids=run_ids
    )
```

**New View:** Create `backend/app/views/research_results.py`:
```python
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlmodel import Session, select
from app.core.dependencies import get_main_session
from app.services.execution_service import ExecutionService

router = APIRouter(tags=["research_results"])

async def get_execution_service():
    return ExecutionService()

@router.get("/{run_id}", response_class=HTMLResponse)
async def view_results(
    run_id: str,
    request: Request,
    session: Session = Depends(get_main_session),
    service: ExecutionService = Depends(get_execution_service)
):
    run_state = service.get_state(run_id)
    
    if not run_state:
        raise HTTPException(status_code=404, detail="Research run not found")
    
    # Fetch artifacts created by this run
    artifact_queries = []
    for result in run_state.get("research_results", []):
        artifact_id = result.get("artifact_id")
        if artifact_id:
            artifact_queries.append(select(Artifact).where(Artifact.id == artifact_id))
    
    # Combine queries and fetch artifacts
    if artifact_queries:
        combined_query = select(Artifact).where(
            Artifact.id.in_([r.get("artifact_id") for r in run_state.get("research_results", [])])
        )
        artifacts = session.exec(combined_query).all()
    else:
        artifacts = []
    
    return {
        "run": run_state,
        "artifacts": artifacts,
        "evidence": session.exec(select(Evidence)).all(),
    }
```

---

### Fix #3: Missing Error Handling in View Layer

**Problem:** No try/catch blocks around business logic.

**File:** `backend/app/views/worlds.py`

**Implementation Pattern:**
```python
@app.post("/batch-research", response_class=HTMLResponse)
async def batch_research(
    request: Request,
    background_tasks: BackgroundTasks,
    world_names: str = Form(...),
):
    from fastapi import HTTPException
    
    try:
        names = [w.strip() for w in world_names.split(",") if w.strip()]
        
        if not names:
            raise HTTPException(status_code=400, detail="No worlds provided")
        
        # ... existing logic
        
    except ValueError as e:
        logger.exception(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Research failed")
```

---

### Fix #4: Pagination Broken

**Problem:** Template has pagination UI but backend ignores offset/limit.

**Solution:** Already covered in Fix #1 - add page/offset parameters to the endpoint.

---

### Fix #5: Database Indices

**Problem:** Slow artifact relation queries.

**File:** `backend/app/db/schema.py`

**Implementation:**
```python
class ArtifactRelation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(
        sa_column=Column(ForeignKey("universe.id", ondelete="CASCADE"), nullable=False)
    )
    from_artifact_id: int = Field(
        sa_column=Column(
            ForeignKey("artifact.id", ondelete="CASCADE"),
            nullable=False, 
            index=True,  # Already exists ✅
        )
    )
    to_artifact_id: int = Field(
        sa_column=Column(
            ForeignKey("artifact.id", ondelete="CASCADE"),
            nullable=False,
            index=True,  # Already exists ✅
        )
    )
    relation_type: str = Field(index=True)  # Already exists ✅
    
    # Add composite index for common queries
    __table_args__ = (
        Index('idx_relation_source', 'from_artifact_id'),
        Index('idx_relation_target', 'to_artifact_id'),
        Index('idx_relation_type_source', 'relation_type', 'from_artifact_id'),
    )
```

**Additional indices for other tables:**
```python
class Artifact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    universe_id: int = Field(index=True)  # Add this
    # ... rest of fields
```

---

### Fix #6: Input Validation

**Problem:** Forms accept invalid data without validation.

**File:** `backend/app/views/worlds.py`

**Implementation:**
```python
from pydantic import BaseModel, Field, ValidationError
from fastapi import HTTPException

# Define validation schemas
class WorldBatchRequest(BaseModel):
    world_ids: list[str] = Field(
        ..., 
        min_items=1, 
        max_items=100,
        each=lambda v: bool(v) and len(v) == 36  # Basic UUID validation
    )
    
class WorldCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=100)
    franchise: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=100)
    continuity: str | None = Field(None, max_length=500)
    era: str | None = Field(None, max_length=100)
    summary: str | None = Field(None, max_length=2000)

@app.post("/worlds/batch-research")
async def batch_research(
    request: WorldBatchRequest,
    background_tasks: BackgroundTasks,
):
    try:
        validated = request.model_validate(request.body)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())
    
    # Use validated data
    run_ids = []
    for world_id in validated.world_ids:
        run_id = str(uuid.uuid4())
        background_tasks.add_task(run_pipeline_in_background, run_id, [world_id])
        run_ids.append({"run_id": run_id, "world": world_id})
    
    return {"run_ids": run_ids}
```

---

### Fix #7: Cookie Validation

**Problem:** Cookie accepts any string value.

**File:** `backend/app/views/research.py`

**Implementation:**
```python
from uuid import UUID as PyUUID

@app.get("/", response_class=HTMLResponse)
async def research_page(request: Request):
    active_world = request.cookies.get("active_world_id")
    
    # Validate cookie if present
    if active_world:
        try:
            PyUUID(active_world)
        except ValueError:
            # Clear invalid cookie and redirect
            response = Response()
            response.delete_cookie("active_world_id")
            raise HTTPException(status_code=400, detail="Invalid world ID")
    
    # ... existing logic
```

---

## 🟡 TRACK 2: USER EXPERIENCE

### Fix #8: Navigation Confusion

**Strategy:** Transform `/worlds` to "World Directory" with search/filter.

**Files to Modify:**
- `backend/app/views/worlds.py` (transform to directory view)
- `backend/templates/pages/worlds.html` (update UI)

**Implementation:**
```python
# worlds.py - Transform to directory listing
@app.get("/", response_class=HTMLResponse)
async def worlds_directory_page(request: Request):
    """World Directory - Browse all universes with search and filters"""
    template = templates.env.get_template("pages/worlds.html")
    return HTMLResponse(content=template.render(
        request=request, 
        current_path=str(request.url.path),
        page_title="World Directory",
        subtitle="Browse and manage all universes"
    ))

@app.get("/search-worlds", response_class=HTMLResponse)
async def search_worlds(
    request: Request,
    query: str = Query(...),
    page: int = Query(default=1),
    per_page: int = Query(default=50),
):
    """Searchable world directory"""
    offset = (page - 1) * per_page
    
    uni_service = UniverseService()
    results = uni_service.search_universes(query=query, limit=per_page, offset=offset)
    total = uni_service.count_universes(query=query)
    
    return render_worlds_table(
        request, 
        results,
        query=query,
        page=page,
        per_page=per_page,
        total=total,
        is_search=True
    )
```

**Template Update (`worlds.html`):**
```html
<div class="mb-6">
    <h1 class="text-xl font-bold mb-4">🌍 World Directory</h1>
    
    <!-- Search Bar -->
    <div class="flex gap-2">
        <input type="text" id="search-input" placeholder="Search worlds by name, franchise..." 
               class="flex-1 px-3 py-2 border rounded-sm">
        <button onclick="performSearch()" class="px-4 py-2 bg-blue-600 text-white rounded-sm">
            🔍 Search
        </button>
    </div>
    
    <!-- Filters -->
    <div class="flex gap-2 mt-2">
        <select id="franchise-filter" class="px-3 py-2 border rounded-sm">
            <option value="">All Franchises</option>
            <option value="Marvel">Marvel</option>
            <option value="DC">DC</option>
        </select>
        <select id="explored-filter" class="px-3 py-2 border rounded-sm">
            <option value="">All Universes</option>
            <option value="true">Explored Only</option>
            <option value="false">Unexplored Only</option>
        </select>
    </div>
</div>
```

---

### Fix #9: Active World State Visibility

**Problem:** Cookie-based state with no visible UI selector.

**Files to Modify:**
- `backend/app/views/research.py`
- `backend/templates/pages/research.html`

**Implementation:**
```python
# research.py - Add helper function
def get_active_world_display(request: Request):
    active_world_id = request.cookies.get("active_world_id")
    
    if not active_world_id:
        return {"display": "All Worlds", "active": False}
    
    try:
        world = uni_service.get_universe_by_uuid(active_world_id)
        if world:
            return {
                "display": world.name,
                "active": True,
                "uuid": active_world_id
            }
    except:
        pass
    
    return {"display": "Unknown World", "active": False}

# Add to template context
@app.get("/", response_class=HTMLResponse)
async def research_page(request: Request):
    active_world_data = get_active_world_display(request)
    
    return HTMLResponse(content=template.render(
        request=request,
        current_path=str(request.url.path),
        active_world=active_world_data["display"],
        has_active_world=active_world_data["active"]
    ))
```

**Template Update (`research.html`):**
```html
<!-- Add to header/navigation -->
<div class="h-12 bg-blue-50 dark:bg-blue-900/20 border-b border-blue-200 px-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
        <span class="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase">Focus:</span>
        <select id="world-selector" 
                name="active_world"
                hx-post="/worlds/set-active-world"
                hx-trigger="change"
                hx-include="this"
                hx-swap="none"
                {% if has_active_world %}class="bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-700"{% endif %}>
            <option value="">--- All Universes ---</option>
            {% for world in worlds %}
                <option value="{{ world.uuid }}" 
                        {% if world.uuid == active_world %}selected{% endif %}>
                    {{ world.name }}
                </option>
            {% endfor %}
        </select>
    </div>
    
    <!-- Show active state indicator -->
    {% if has_active_world %}
    <div class="flex items-center gap-2 text-green-600 dark:text-green-400">
        <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
        <span class="text-sm">{{ active_world }}</span>
    </div>
    {% endif %}
</div>
```

---

### Fix #10: Research Results Viewer (NEW PAGE)

**New Page:** `/research/results/{run_id}`

**Files to Create:**
- `backend/app/views/research_results.py`
- `backend/templates/pages/research_results.html`

**Implementation:**
```python
# research_results.py
from fastapi import APIRouter, Depends, Query, Request, HTTPException, Response
from sqlmodel import Session, select
from app.core.dependencies import get_main_session
from app.services.execution_service import ExecutionService
from app.db.schema import Artifact, Evidence, ArtifactRelation

router = APIRouter(tags=["research_results"])

@router.get("/{run_id}", response_class=HTMLResponse)
async def view_research_results(
    run_id: str,
    request: Request,
    session: Session = Depends(get_main_session),
    service: ExecutionService = Depends(get_execution_service)
):
    """View all results from a specific research run"""
    
    # Get run state
    run_state = service.get_state(run_id)
    
    if not run_state:
        raise HTTPException(status_code=404, detail="Research run not found")
    
    # Determine run status
    status_map = {
        RunPhase.FINISHED: "completed",
        RunPhase.RESEARCH: "in_progress",
        RunPhase.DB_INTEGRATION: "integrating",
        RunPhase.SUMMARY: "summarizing",
    }
    
    status = status_map.get(run_state.get("active_task"), "unknown")
    
    # Fetch artifacts created by this run
    artifact_ids = [r.get("artifact_id") for r in run_state.get("research_results", []) if r.get("artifact_id")]
    
    artifacts = []
    if artifact_ids:
        artifacts = session.exec(
            select(Artifact).where(Artifact.id.in_(artifact_ids))
        ).all()
    
    # Fetch evidence related to these artifacts
    artifact_ids_list = [a.id for a in artifacts]
    evidence = session.exec(
        select(Evidence).where(Evidence.artifact_id.in_(artifact_ids_list))
    ).all()
    
    return {
        "run": run_state,
        "artifacts": artifacts,
        "evidence": evidence,
        "status": status,
        "artifact_count": len(artifacts),
        "evidence_count": len(evidence),
    }

@router.post("/{run_id}/delete")
async def delete_research_run(
    run_id: str,
    session: Session = Depends(get_main_session),
    service: ExecutionService = Depends(get_execution_service)
):
    """Delete a completed research run"""
    
    try:
        service.delete_state(run_id)
        return {"success": True}
    except Exception as e:
        logger.exception(f"Failed to delete run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete run")
```

**Template (`research_results.html`):**
```html
<div class="p-4">
    <div class="flex justify-between items-center mb-6">
        <h1 class="text-xl font-bold">📊 Research Results</h1>
        <div class="flex gap-2">
            <span class="px-3 py-1 rounded-full {% if status == 'completed' %}bg-green-100 text-green-800{% elif status == 'in_progress' %}bg-blue-100 text-blue-800 animate-pulse{% else %}bg-gray-100 text-gray-800{% endif %}">
                {{ status|title }}
            </span>
            <a href="/research" class="px-3 py-1 bg-blue-600 text-white rounded-sm">← Back</a>
            <button onclick="deleteRun()" class="px-3 py-1 bg-red-600 text-white rounded-sm">Delete</button>
        </div>
    </div>
    
    <!-- Run Metadata -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-sm">
        <div>
            <span class="text-xs text-gray-500">Run ID</span>
            <span class="font-mono text-sm">{{ run.run_id }}</span>
        </div>
        <div>
            <span class="text-xs text-gray-500">Started</span>
            <span class="text-sm">{{ run.started_at }}</span>
        </div>
        <div>
            <span class="text-xs text-gray-500">Worlds</span>
            <span class="text-sm">{{ run.target_worlds|length }}</span>
        </div>
        <div>
            <span class="text-xs text-gray-500">Artifacts</span>
            <span class="text-sm font-bold text-blue-600">{{ artifact_count }}</span>
        </div>
    </div>
    
    <!-- Artifacts List -->
    <div id="artifacts-container">
        {% for artifact in artifacts %}
        <div class="border border-gray-200 dark:border-gray-700 rounded-sm p-4 mb-2">
            <div class="flex justify-between items-start">
                <div>
                    <h3 class="font-semibold">{{ artifact.name }}</h3>
                    <span class="text-xs text-gray-500">Type: {{ artifact.type }}</span>
                    {% if artifact.payload_json %}
                    <div class="mt-2 p-2 bg-gray-50 dark:bg-gray-900 rounded-sm text-xs overflow-auto max-h-40">
                        {{ artifact.payload_json[:200] }}...
                    </div>
                    {% endif %}
                </div>
                <div class="flex gap-2">
                    <a href="/knowledge?artifact={{ artifact.id }}" class="px-2 py-1 bg-green-600 text-white text-xs rounded-sm">View in Knowledge</a>
                </div>
            </div>
            
            <!-- Evidence Section -->
            {% for evidence in evidence %}
            {% if evidence.artifact_id == artifact.id %}
            <div class="mt-3 p-2 bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500 ml-6">
                <div class="flex justify-between">
                    <span class="text-xs font-semibold text-yellow-700 dark:text-yellow-300">📄 Evidence</span>
                    <a href="{{ evidence.source_url }}" target="_blank" class="text-xs text-blue-600 hover:underline">View Source →</a>
                </div>
                <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">{{ evidence.section }}</p>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>
    
    <!-- Empty State -->
    {% if not artifacts %}
    <div class="text-center py-12 text-gray-500">
        <p>No artifacts generated yet. Check back later.</p>
    </div>
    {% endif %}
</div>

<script>
function deleteRun() {
    if (confirm('Delete this research run? This cannot be undone.')) {
        fetch(`/research/results/{{ run_id }}/delete`, {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    window.location.href = '/research';
                } else {
                    alert('Failed to delete');
                }
            });
    }
}
</script>
```

---

## 🟢 TRACK 3: POLISH & DOCUMENTATION

### Fix #11: Onboarding Flow

**New View:** `backend/app/views/onboarding.py`

```python
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(tags=["onboarding"])

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "pages"

@router.get("/welcome", response_class=HTMLResponse)
async def onboarding_welcome(request: Request):
    """First-time user welcome and tutorial"""
    
    has_visited = request.cookies.get("onboarding_completed")
    
    if has_visited:
        return Response(
            content="<script>window.location.href='/research'</script>",
            status_code=302
        )
    
    template = TEMPLATE_DIR / "onboarding.html"
    return HTMLResponse(content=template.render())
```

**Template (`onboarding.html`):**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to Omniverse V2</title>
</head>
<body class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <div class="max-w-3xl mx-auto p-8">
        <div class="mb-8 p-6 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 rounded-r-lg">
            <h1 class="text-2xl font-bold text-blue-900 dark:text-blue-100 mb-2">🎯 Welcome to Omniverse V2</h1>
            <p class="text-blue-800 dark:text-blue-200">A fictional power-tiering platform for comparing universes, characters, and their abilities.</p>
        </div>
        
        <div class="space-y-6">
            <!-- Step 1 -->
            <div class="flex gap-4">
                <div class="flex-shrink-0 w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold text-xl">1</div>
                <div class="flex-1">
                    <h3 class="font-semibold text-lg mb-2">Browse Universes</h3>
                    <p class="text-gray-700 dark:text-gray-300">Navigate to the Research section to browse or import universes from popular franchises.</p>
                </div>
            </div>
            
            <!-- Step 2 -->
            <div class="flex gap-4">
                <div class="flex-shrink-0 w-12 h-12 bg-green-600 text-white rounded-full flex items-center justify-center font-bold text-xl">2</div>
                <div class="flex-1">
                    <h3 class="font-semibold text-lg mb-2">Submit Research</h3>
                    <p class="text-gray-700 dark:text-gray-300">Use AI agents to research each universe. Submit claims about power levels, abilities, and lore.</p>
                </div>
            </div>
            
            <!-- Step 3 -->
            <div class="flex gap-4">
                <div class="flex-shrink-0 w-12 h-12 bg-purple-600 text-white rounded-full flex items-center justify-center font-bold text-xl">3</div>
                <div class="flex-1">
                    <h3 class="font-semibold text-lg mb-2">Explore Results</h3>
                    <p class="text-gray-700 dark:text-gray-300">View collected evidence in the Knowledge Graph and compare findings across universes.</p>
                </div>
            </div>
            
            <!-- Step 4 -->
            <div class="flex gap-4">
                <div class="flex-shrink-0 w-12 h-12 bg-orange-600 text-white rounded-full flex items-center justify-center font-bold text-xl">4</div>
                <div class="flex-1">
                    <h3 class="font-semibold text-lg mb-2">Start Tiering (Soon)</h3>
                    <p class="text-gray-700 dark:text-gray-300">Once you have enough data, use the Tiering tool to rank universes against a standard rubric.</p>
                </div>
            </div>
        </div>
        
        <div class="mt-8 text-center">
            <a href="/research" class="inline-block px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-sm">
                Get Started →
            </a>
        </div>
    </div>
</body>
</html>
```

---

### Fix #12: Documentation/Docstrings

**Scope:** Add docstrings to all critical functions.

**Pattern Template:**
```python
def function_name(param1, param2=None):
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter (optional)
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this exception is raised
    
    Example:
        >>> function_name("example", "arg2")
        {'result': 'success'}
    
    Notes:
        - Any important notes or caveats
        - Dependencies on external services
        - Performance considerations
    """
    # Implementation
```

**Functions Requiring Docstrings:**
1. `batch_research()` in worlds.py
2. `database_worlds()` in worlds.py
3. `research_page()` in research.py
4. `get_active_world_display()` in research.py
5. All CRUD endpoints in API routers
6. Service methods in universe_service.py

---

## 📊 TESTING STRATEGY

### Unit Tests
- [ ] Pagination logic for `/worlds/database-worlds`
- [ ] Input validation schemas
- [ ] Cookie UUID validation
- [ ] Background task error handling

### Integration Tests
- [ ] Full research workflow with pagination
- [ ] Research results view end-to-end
- [ ] World directory search functionality

### Manual Testing Checklist
- [ ] Navigate from Home → Research → Results
- [ ] Search/filter worlds on directory page
- [ ] Verify active world selector updates UI
- [ ] Test pagination with large dataset (1000+ worlds)
- [ ] Simulate research failure and verify error message

---

## ⏰ IMPLEMENTATION TIMELINE

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Week 1** | Backend Stability | Fixes #1, #2, #3, #4, #5, #6, #7 |
| **Week 2** | UX Improvements | Fixes #8, #9, #10 (Results Viewer) |
| **Week 3** | Polish | Fix #11 (Onboarding), Fix #12 (Docstrings) |
| **Week 4** | QA & Testing | Integration tests, manual testing, documentation |

**Total Estimated Effort: 26-36 hours**

---

## ✅ APPROVAL REQUIRED

Before implementation begins, please confirm:

1. Transform `/worlds` to World Directory ✓
2. Create full implementation spec document ✓
3. Parallel tracks (backend + UX) ✓
4. No deadline constraint ✓

**Ready to proceed with implementation when you give the go-ahead!**

