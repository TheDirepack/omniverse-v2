# Omniverse V2 API and HTMX Views

V2 provides JSON at `/api/v2` and HTML/HTMX routes without a version prefix. `backend/app/v2/main.py` includes views before the API router.

## JSON API

`backend/app/v2/api.py` defines the `/api/v2` router.

| Area | Routes |
|---|---|
| Health/logging | `GET /health`, `GET/PUT /settings/logging`, client-error post, `GET /logs/{server\|agent}` |
| Worlds | `GET /worlds` |
| Providers | provider CRUD, model upsert, credential create/delete |
| Routes/health | route put/delete, candidate and credential health resets |
| Runs | create, get/list, cancel, resume, retry, flow, events, summary |
| Research reads | canon, evidence, provenance, relationships, gaps/conflicts, coverage |

`POST /research-runs` requires `Idempotency-Key`, returns `202`, and sets `Location: /api/v2/runs/{id}`. Conflicting idempotency keys and invalid transitions return `409`; missing runs return `404`; runtime-backed logging endpoints return `503` if no runtime exists.

## HTMX views

`backend/app/v2/views.py` renders `backend/app/templates/`.

| Area | Key routes |
|---|---|
| Research | `/`, `/research/`, `/research/worlds`, `/research/runs`, `/research/runs/{run_id}` |
| Knowledge | `/knowledge/`, `/knowledge/{world_id}/{tab}`, `/provenance/{node_id}`, `/validation/` |
| Operations | `/flow/`, `/flow/{run_id}`, `/logs/`, `/settings/` and settings actions |
| Aliases | `/worlds`, `/worlds/`, `/research/choose-world` |

The HTMX run form posts to `/research/runs`, returns `202`, and sets `HX-Retarget: #run-queue`, `HX-Reswap: afterbegin`, and `X-Run-ID`. It accepts form data; the JSON endpoint accepts a request body plus its idempotency header.

`/theory/` exists as a page, but theory and tiering endpoints/workflows are deferred. Static files mount from `backend/app/static/` at `/static`. Middleware returns a valid supplied `X-Request-ID` or a generated value.

See [Runtime and research](RUNTIME_AND_RESEARCH.md).
