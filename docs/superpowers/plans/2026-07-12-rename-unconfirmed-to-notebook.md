# [Rename 'notebook' to 'notebook'] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** System-wide rename of "notebook" to "notebook" to align with the new architecture.

**Architecture:** Sequential rename of files followed by content replacement and verification.

**Tech Stack:** Python (SQLModel/FastAPI), HTML (Jinja2), SQLite.

## Global Constraints
- Do NOT modify historical logs in `backend/tests/logs/`.
- Do NOT modify `researcher_results.txt`.
- Use `notebook` as the primary replacement; `staging` may be used for UI context where appropriate.
- Ensure all imports are updated to match renamed files.

---

### Task 1: File System Migration

**Files:**
- Rename: `backend/app/db/notebook_schema.py` $\rightarrow$ `backend/app/db/notebook_schema.py`
- Rename: `backend/app/db/notebook_session.py` $\rightarrow$ `backend/app/db/notebook_session.py`
- Rename: `backend/data/notebook.db` $\rightarrow$ `backend/data/notebook.db`
- Rename: `backend/app/templates/fragments/notebook_claim_card.html` $\rightarrow$ `backend/app/templates/fragments/notebook_claim_card.html`
- Rename: `backend/app/templates/fragments/notebook_artifact_card.html` $\rightarrow$ `backend/app/templates/fragments/notebook_artifact_card.html`
- Rename: `backend/tests/backend/test_notebook_provenance.py` $\rightarrow$ `backend/tests/backend/test_notebook_provenance.py`

- [ ] **Step 1: Rename DB and Schema files**
  `mv backend/app/db/notebook_schema.py backend/app/db/notebook_schema.py`
  `mv backend/app/db/notebook_session.py backend/app/db/notebook_session.py`
  `mv backend/data/notebook.db backend/data/notebook.db`

- [ ] **Step 2: Rename Template fragments**
  `mv backend/app/templates/fragments/notebook_claim_card.html backend/app/templates/fragments/notebook_claim_card.html`
  `mv backend/app/templates/fragments/notebook_artifact_card.html backend/app/templates/fragments/notebook_artifact_card.html`

- [ ] **Step 3: Rename Test files**
  `mv backend/tests/backend/test_notebook_provenance.py backend/tests/backend/test_notebook_provenance.py`

- [ ] **Step 4: Commit**
  `git add .`
  `git commit -m "refactor: rename notebook files to notebook"`

### Task 2: Database Schema & Session Refactor

**Files:**
- Modify: `backend/app/db/notebook_schema.py`
- Modify: `backend/app/db/notebook_session.py`
- Modify: `backend/app/db/session.py`

- [ ] **Step 1: Update `notebook_schema.py`**
  Replace `notebook_metadata` $\rightarrow$ `notebook_metadata`
  Replace `NotebookModel` $\rightarrow$ `NotebookModel`
  Replace `NotebookUniverse` $\rightarrow$ `NotebookUniverse`
  Replace `NotebookClaim` $\rightarrow$ `NotebookClaim`
  Update `__tablename__ = "notebook_universe"` $\rightarrow$ `__tablename__ = "notebook_universe"`

- [ ] **Step 2: Update `notebook_session.py`**
  Replace `notebook_metadata` $\rightarrow$ `notebook_metadata`
  Replace `NOTEBOOK_DB_URL` $\rightarrow$ `NOTEBOOK_DB_URL`
  Replace `notebook.db` $\rightarrow$ `notebook.db`
  Replace `notebook_engine` $\rightarrow$ `notebook_engine`
  Replace `init_notebook_db` $\rightarrow$ `init_notebook_db`
  Replace `get_notebook_session` $\rightarrow$ `get_notebook_session`

- [ ] **Step 3: Update `backend/app/db/session.py`**
  Update import: `from app.db.notebook_session import init_notebook_db` $\rightarrow$ `from app.db.notebook_session import init_notebook_db`
  Update call: `init_notebook_db()` $\rightarrow$ `init_notebook_db()`

- [ ] **Step 4: Commit**
  `git commit -m "refactor: update schema and session names to notebook"`

### Task 3: Core Logic & Repository Refactor

**Files:**
- Modify: `backend/app/core/dependencies.py`
- Modify: `backend/app/services/research_workspace.py`
- Modify: `backend/app/services/ocr_service.py`
- Modify: `backend/app/services/effect_executor.py`
- Modify: `backend/app/repositories/acquisition_cache.py`

- [ ] **Step 1: Update `dependencies.py`**
  Update import: `from app.db.notebook_session import get_notebook_session` $\rightarrow$ `from app.db.notebook_session import get_notebook_session`
  Rename function: `get_notebook_session` $\rightarrow$ `get_notebook_session`

- [ ] **Step 2: Update `research_workspace.py`**
  Update imports from `notebook_schema` and `notebook_session` to `notebook_schema` and `notebook_session`.
  Replace `notebook_engine` $\rightarrow$ `notebook_engine`.

- [ ] **Step 3: Update `ocr_service.py`**
  Update import: `from app.db.notebook_schema import AcquisitionArtifact` $\rightarrow$ `from app.db.notebook_schema import AcquisitionArtifact`.

- [ ] **Step 4: Update `effect_executor.py`**
  Replace string `"Clean up notebook staging"` $\rightarrow$ `"Clean up notebook staging"`.

- [ ] **Step 5: Update `acquisition_cache.py`**
  Update imports to `notebook_schema` and `notebook_session`.
  Replace `notebook_engine` $\rightarrow$ `notebook_engine`.

- [ ] **Step 6: Commit**
  `git commit -m "refactor: update core logic and repositories to notebook"`

### Task 4: View & UI Refactor

**Files:**
- Modify: `backend/app/views/validation.py`
- Modify: `backend/app/views/provenance.py`
- Modify: `backend/app/views/flow.py`
- Modify: `backend/app/views/settings.py`
- Modify: `backend/app/templates/pages/validation.html`
- Modify: `backend/app/templates/pages/provenance.html`
- Modify: `backend/app/templates/fragments/notebook_claim_card.html`
- Modify: `backend/app/templates/fragments/notebook_artifact_card.html`
- Modify: `backend/app/templates/fragments/flow_step.html`

- [ ] **Step 1: Update Python Views**
  In `validation.py`, `provenance.py`, `flow.py`, `settings.py`:
  - Replace `get_notebook_session` $\rightarrow$ `get_notebook_session`
  - Replace `notebook_schema` $\rightarrow$ `notebook_schema`
  - Replace `notebook_session` $\rightarrow$ `notebook_session`
  - Replace `notebook_engine` $\rightarrow$ `notebook_engine`
  - Update endpoint paths if they contain `/notebook/` $\rightarrow$ `/notebook/`.

- [ ] **Step 2: Update HTML Templates**
  - In all `.html` files: Replace `notebook` $\rightarrow$ `notebook` (or `staging` for user-facing text).
  - Update fragment includes: `fragments/notebook_...` $\rightarrow$ `fragments/notebook_...`.

- [ ] **Step 3: Commit**
  `git commit -m "refactor: update views and templates to notebook"`

### Task 5: Tests & Scripts Refactor

**Files:**
- Modify: `backend/scripts/cleanup_worlds_general.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/ui/test_validation_ui.py`
- Modify: `backend/tests/ui/test_workspace_views.py`
- Modify: `test.sh`

- [ ] **Step 1: Update `cleanup_worlds_general.py`**
  Update imports and replace `notebook` $\rightarrow$ `notebook`.

- [ ] **Step 2: Update `conftest.py`**
  Replace `TEST_UNCONFIRMED_URL` $\rightarrow$ `TEST_NOTEBOOK_URL`.
  Replace `notebook_engine` $\rightarrow$ `notebook_engine`.
  Update SQLite table cleanup: `DELETE FROM notebook_universe` $\rightarrow$ `DELETE FROM notebook_universe`.

- [ ] **Step 3: Update UI Tests**
  In `test_validation_ui.py` and `test_workspace_views.py`:
  - Update imports and replace `notebook` $\rightarrow$ `notebook`.

- [ ] **Step 4: Update `test.sh`**
  Update `MAIN_DBS` array: `"notebook.db"` $\rightarrow$ `"notebook.db"`.
  Update `TEMP_DB_FILES` array: `"/tmp/omniverse_test_notebook.db"` $\rightarrow$ `"/tmp/omniverse_test_notebook.db"`.

- [ ] **Step 5: Commit**
  `git commit -m "refactor: update tests and scripts to notebook"`

### Task 6: Final Verification

- [ ] **Step 1: Linting**
  Run `./lint.sh`
  Expected: PASS

- [ ] **Step 2: Strict Linting**
  Run `./lint.sh --strict`
  Expected: PASS

- [ ] **Step 3: Full Test Suite**
  Run `./test.sh`
  Expected: PASS

- [ ] **Step 4: Final Commit**
  `git commit -m "chore: complete notebook to notebook rename"`
