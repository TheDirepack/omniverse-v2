# Design: Rename 'notebook' to 'notebook'

## Context
The project is moving from an "notebook" concept to a "notebook" concept to align with the new architecture. This requires a system-wide rename of files, variables, classes, and UI text.

## Goals
- Replace all occurrences of `notebook` with `notebook` in the codebase.
- Ensure no imports are broken.
- Update database filenames and references.
- Update user-facing UI text.
- Maintain existing historical logs and result files.

## Scope

### 1. File Renaming
The following files (and any others containing `notebook`) will be renamed:
- `backend/app/db/notebook_schema.py` $\rightarrow$ `backend/app/db/notebook_schema.py`
- `backend/app/db/notebook_session.py` $\rightarrow$ `backend/app/db/notebook_session.py`
- `backend/data/notebook.db` $\rightarrow$ `backend/data/notebook.db`
- `backend/app/templates/fragments/notebook_claim_card.html` $\rightarrow$ `backend/app/templates/fragments/notebook_claim_card.html`
- `backend/app/templates/fragments/notebook_artifact_card.html` $\rightarrow$ `backend/app/templates/fragments/notebook_artifact_card.html`
- `backend/tests/backend/test_notebook_provenance.py` $\rightarrow$ `backend/tests/backend/test_notebook_provenance.py`

### 2. Code Refactoring
Replace the following strings (case-sensitive where appropriate):
- `notebook_schema` $\rightarrow$ `notebook_schema`
- `notebook_session` $\rightarrow$ `notebook_session`
- `notebook_engine` $\rightarrow$ `notebook_engine`
- `get_notebook_session` $\rightarrow$ `get_notebook_session`
- `NotebookModel` $\rightarrow$ `NotebookModel`
- `NotebookUniverse` $\rightarrow$ `NotebookUniverse`
- `NotebookClaim` $\rightarrow$ `NotebookClaim`
- `NOTEBOOK_DB_URL` $\rightarrow$ `NOTEBOOK_DB_URL`

### 3. UI & Template Updates
- Replace all `notebook` text in HTML files with `notebook` or `staging`.
- Update fragment paths in templates.

### 4. Database & Test Config
- `test.sh`: Update DB lists and temp file paths.
- `backend/tests/conftest.py`: Update `TEST_UNCONFIRMED_URL` $\rightarrow$ `TEST_NOTEBOOK_URL`.

## Exclusions
- `backend/tests/logs/`
- `researcher_results.txt`

## Verification Plan
1. Run `./lint.sh` (Ruff) to check for syntax and basic import errors.
2. Run `./lint.sh --strict` (Mypy) to verify type safety and deep imports.
3. Run `./test.sh` to verify all tests pass.
