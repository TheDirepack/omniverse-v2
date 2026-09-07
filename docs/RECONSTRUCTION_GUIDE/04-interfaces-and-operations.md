# 4. Interfaces and operations

## HTTP surfaces

JSON is available only under `/api/v2`. Principal resource families are:

| Family | Operations |
|---|---|
| health/logs | health; get/put logging settings; client error ingest; server/agent log reads |
| worlds | searchable/paginated world listing |
| providers | provider CRUD, model upsert, credential create/delete, routes, route health reset |
| research runs | create (`202`, idempotency key, `Location`), list/get, cancel, resume, retry, flow, events, summary |
| knowledge | canon, evidence, provenance, relationships, workspace gaps/conflicts, coverage |

Errors follow FastAPI responses: missing resources are `404`, invalid state or
idempotency conflicts are `409`, and runtime-dependent log reads report `503` when
there is no runtime. `api.py` contains the exact Pydantic request/response projection
schemas and must remain the source of truth for a generated client.

Unversioned Jinja routes provide `/`, `/research/`, run queue/detail/actions,
`/knowledge/`, `/provenance/{node_id}`, `/validation/`, `/flow/`, `/logs/`,
`/settings/`, and `/theory/`. The research form posts to `/research/runs` and returns
an HTML fragment with `202`, `HX-Retarget: #run-queue`, `HX-Reswap: afterbegin`, and
`X-Run-ID`. Templates are in `backend/app/templates/pages` (full shells) and
`backend/app/templates/v2` (fragments/settings); `base.html`, `main.css`, and
`htmx-values.js` supply the shared UI shell. Do not introduce a frontend build step.

## Configuration

`V2Config.from_env()` reads `OMNIVERSE_V2_*` values. The essential settings are
database/blob/credential/seed paths, SQLite timeout, worker poll/concurrency/reclaim,
loopback and bind host, HTTP/body limits, browser/PDF/OCR limits, preprocessing and
SSH settings, Qwen endpoint/model/context, logging root/path, and cache TTL. Relative
paths resolve beneath `backend`; environment values override UI persistence. Default
cache freshness is seven days.

Loopback-only access is required unless `OMNIVERSE_V2_REQUIRE_LOOPBACK=false` is an
intentional deployment decision. All URL and logging input must preserve the existing
redaction, size bounds, path validation, and HTML escaping behaviour.

## Rebuild sequence

1. Create the package/venv and install FastAPI, Uvicorn, SQLAlchemy 2, Alembic,
   Pydantic, HTTPX, Jinja2, multipart support, HTML parsing, PDF and OCR libraries.
2. Implement config with no network/database side effects at import time.
3. Define domain enums/transitions and strict Pydantic contracts, then ORM tables and
   migrations. Add foreign-key, WAL, seed-head, and immutable-record validation.
4. Add content-addressed blobs, credential references, seed import, initialization,
   online backup/restore, and guarded reset services.
5. Implement run kernel leasing/idempotency/checkpointing before any model workflow.
6. Add URL-safe acquisition, deterministic preprocessing, evidence validation, and
   provider routing/gateway. Treat model output as untrusted until contract-validated.
7. Build the workflow step-by-step with effects and restart tests. Add projections,
   API, then HTMX views/templates.
8. Add lifecycle orchestration and structured redacted logging; only then enable live
   adapters and optional remote model lifecycle.

## Verification contract

Run `./test.sh` for V2 fast offline tests, `./test.sh --ui` for UI tests,
`./test.sh --slow` for slow non-network tests, `./test.sh --evaluation` for evaluation
tests, and `./lint.sh` (or `--strict`). Tests under `backend/tests_v2/` are executable
requirements: they cover boundaries, schema migration/seed, immutability, backup,
concurrency, provider fallback, acquisition security/cache derivatives, research
correctness/restart behaviour, logging/redaction, API contracts, settings diagnostics,
and rendered UI interactions.

The minimum acceptance test for a rebuild is: initialize an empty store; create a
multi-target idempotent run; survive a restart after any workflow step; show its flow
and provenance; reject fabricated/MiniCPM-only evidence; promote accepted fields to
immutable canon; and keep secrets out of database/API/logs.
