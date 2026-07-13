# Graph-Based Hierarchical Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition from flat metadata columns on `Universe` to a flexible graph-based hierarchy using `Artifact` and `ArtifactRelation`.

**Architecture:** Move organizational metadata (franchise, era, etc.) into polymorphic `Artifact` nodes. Use `ArtifactRelation` to define parent-child and other hierarchical relationships. Update `KnowledgeRetrieverService` to perform graph-distance-based context building.

**Tech Stack:** Python, SQLModel (SQLAlchemy), FastAPI, pytest.

## Global Constraints

- Follow existing code style and patterns.
- Maintain `Universe` as the top-level container.
- Ensure all changes are verified with tests.

---

### Task 1: Schema Refactor & Migration Utility

**Files:**
- Modify: `backend/app/db/schema.py`
- Create: `backend/scripts/migrate_universe_metadata_to_artifacts.py`
- Test: `backend/tests/backend/test_db.py`

**Interfaces:**
- Consumes: `Universe` model, `Artifact` model, `ArtifactRelation` model.
- Produces: Updated `Universe` schema, populated `Artifact` hierarchy.

- [ ] **Step 1: Write the failing test**

```python
def test_universe_metadata_columns_removed():
    # Assert that Universe model no longer has franchise, category, continuity, era
    assert not hasattr(Universe, "franchise")
    assert not hasattr(Universe, "category")
    assert not hasattr(Universe, "continuity")
    assert not hasattr(Universe, "era")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/backend/test_db.py::test_universe_metadata_columns_removed -v`
Expected: FAIL with "AttributeError: type object 'Universe' has no attribute 'franchise'"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/db/schema.py
# Remove the following lines from Universe class:
# franchise: str | None = None
# category: str | None = None
# continuity: str | None = None
# era: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/backend/test_db.py::test_universe_metadata_columns_removed -v`
Expected: PASS

- [ ] **Step 5: Implement Migration Script**

Create `backend/scripts/migrate_universe_metadata_to_artifacts.py` that:
1. Connects to the database.
2. Iterates through all `Universe` records.
3. For each universe:
   - If `franchise` is set, create an `Artifact(type="franchise", name=franchise)`.
   - If `category` is set, create an `Artifact(type="category", name=category)`.
   - Create an `Artifact(type="world", name=universe.name)`.
   - Create `ArtifactRelation`s to link them: `world` -> `franchise` (`PART_OF`).
4. Commit changes.

- [ ] **Step 6: Run test to verify migration**

Create a test that:
1. Seeds a Universe with metadata.
2. Runs the migration script.
3. Verifies the `Artifact`s and `ArtifactRelation`s exist in the DB.

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/schema.py backend/scripts/migrate_universe_metadata_to_artifacts.py backend/tests/backend/test_db.py
git commit -m "feat: refactor Universe schema and add migration script"
```

---

### Task 2: Repository & Service Updates (Part 1: Universe management)

**Files:**
- Modify: `backend/app/repositories/universe.py`
- Modify: `backend/app/services/universe_service.py`
- Modify: `backend/app/api/routers/worlds.py` (if necessary)

**Interfaces:**
- Consumes: Updated `Universe` model.
- Produces: Working Universe management API without metadata columns.

- [ ] **Step 1: Write the failing test**

```python
def test_create_universe_without_metadata():
    # Assert that create_universe no longer accepts franchise, category, etc.
    with pytest.raises(TypeError):
        service.create_universe(name="Test Universe", franchise="Test Franchise")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/backend/test_universe_service.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Update `UniverseRepository.create` and `UniverseService.create_universe` to remove metadata parameters.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/backend/test_universe_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/universe.py backend/app/services/universe_service.py
git commit -m "feat: update Universe management to match new schema"
```

---

### Task 3: Repository & Service Updates (Part 2: Artifact & Relation management)

**Files:**
- Modify: `backend/app/repositories/universe.py`
- Modify: `backend/app/services/universe_service.py`

**Interfaces:**
- Consumes: `Artifact`, `ArtifactRelation`.
- Produces: Methods for hierarchical traversal.

- [ ] **Step 1: Write the failing test**

```python
def test_get_artifact_hierarchy():
    # Setup: Create Artifact A (franchise), B (world) linked via PART_OF
    # Assert: get_artifact_hierarchy(B) returns [A]
    hierarchy = repo.get_artifact_hierarchy(B.id)
    assert A.id in hierarchy
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/backend/test_artifact_hierarchy.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Implement `get_artifact_hierarchy` in `UniverseRepository` using recursive CTE or iterative traversal of `ArtifactRelation`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/backend/test_artifact_hierarchy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/universe.py backend/app/services/universe_service.py
git commit -m "feat: add artifact hierarchy traversal"
```

---

### Task 4: Knowledge Retrieval Enhancement

**Files:**
- Modify: `backend/app/services/knowledge_retriever.py`

**Interfaces:**
- Consumes: `ArtifactRelation`, `Artifact`.
- Produces: Enhanced semantic graph with hierarchical context.

- [ ] **Step 1: Write the failing test**

```python
def test_get_universe_knowledge_graph_with_hierarchy():
    # Setup: Entity E in World W, World W in Franchise F.
    # Assert: graph[E] contains facts for E, AND relationship to W and F.
    graph = retriever.get_universe_knowledge_graph(universe_id)
    assert "E" in graph
    assert any(f["predicate"] == "PART_OF" and f["object"] == "W" for f in graph["E"]["facts"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/backend/test_knowledge_retriever.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Update `get_universe_knowledge_graph` to:
1. Fetch all `Artifact`s and `ArtifactRelation`s.
2. For each `Artifact`, traverse its hierarchy (up/down) up to `max_depth`.
3. Add these hierarchical relations as "facts" in the returned graph.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/backend/test_knowledge_retriever.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_retriever.py
git commit -m "feat: enhance knowledge retriever with hierarchical context"
```

---

### Task 5: DB Agent logic update

**Files:**
- Modify: `backend/app/agents/nodes.py` (or where DB Architect logic resides)

**Interfaces:**
- Consumes: Research data.
- Produces: Merged/Linked `Artifact`s and `ArtifactRelation`s.

- [ ] **Step 1: Write the failing test**

```python
def test_db_architect_merging_existing_entity():
    # Setup: Existing Entity E in World W.
    # Research produces new data for E.
    # Assert: E is updated, not duplicated.
    node.run(research_data)
    assert count_artifacts(name="E") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/backend/test_db_architect.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Update DB Architect node to:
1. **Check existence**: Query `Artifact` by name/type within the current hierarchy.
2. **Merge**: If exists, update existing `Artifact` (payload, support, evidence).
3. **Link**: If new, create `Artifact` and create `ArtifactRelation` to its parent (from research/hierarchy context).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/backend/test_db_architect.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/nodes.py
git commit -m "feat: update DB Architect for hierarchical recognition and merging"
```
