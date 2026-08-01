# Omniverse V2 Codemaps

These source-backed codemaps describe the current V2 runtime in `backend/app/v2/`.

| Map | Contents |
|---|---|
| [Architecture](ARCHITECTURE.md) | Facade, app factory, runtime boundaries, deferred scope |
| [Runtime and research](RUNTIME_AND_RESEARCH.md) | Worker, workflow, acquisition, and routing |
| [Persistence](PERSISTENCE.md) | SQLite, Alembic, blobs, credentials, and resets |
| [API and views](API_AND_VIEWS.md) | `/api/v2` JSON and unversioned HTMX routes |
| [Operations](OPERATIONS.md) | Lifecycle, JSONL logs, commands, and tests |

V2 covers research, evidence, canon, provenance, providers, and operations. Tiering and theory are deferred. The `/theory/` page is presentation-only; V2 exposes no theory or tiering API.

**Sources:** [`backend/app/main.py`](../../backend/app/main.py), [`backend/app/v2/main.py`](../../backend/app/v2/main.py), [`runtime.py`](../../backend/app/v2/runtime.py), [`workflow.py`](../../backend/app/v2/workflow.py), and [`models.py`](../../backend/app/v2/models.py).
