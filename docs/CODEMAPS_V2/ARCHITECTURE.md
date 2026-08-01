# Omniverse V2 Architecture

V2 is a FastAPI research system with unversioned HTMX views and a `/api/v2` JSON API over one SQLite database.

## Entrypoints

`backend/app/main.py` is a facade: it imports `create_app` from `backend/app/v2/main.py` and exposes `app` for Uvicorn.

```text
app.main:app -> app.v2.main.create_app()
  -> V2Runtime.build(V2Config.from_env())
  -> unversioned views router
  -> /api/v2 router
```

The factory mounts `/static`, adds request-ID/access-log middleware, and owns the FastAPI lifespan. Startup validates the migrated and seeded schema, applies log settings, reconciles runs, optionally manages remote models, refreshes adapters, and starts the worker. Shutdown stops work, closes adapters and HTTP, closes logs, and disposes SQLite.

## Runtime composition

`V2Runtime` owns the engine, blob store, credential service, provider router, run kernel, query service, acquisition service, workflow, worker, HTTP client, and adapter status.

| Concern | Source |
|---|---|
| Runtime/lifecycle | `backend/app/v2/runtime.py` |
| Configuration | `backend/app/v2/config.py` |
| Run state | `backend/app/v2/research_runs.py` |
| Read projections | `backend/app/v2/projections.py` |
| Templates/views | `backend/app/v2/views.py` and `backend/app/templates/` |

Acquisition and browser adapters sit behind `AcquisitionService`; model adapters sit behind `ProviderRouter`. Immutable provenance records have SQLite triggers and SQLAlchemy flush guards.

## Deferred scope

V2 workflow and JSON API scope is research and canon. Tiering, extrapolation, and theory evaluation are deferred. Do not use legacy `backend/app/workflow/` or `backend/app/views/` as V2 runtime paths.

See [Runtime and research](RUNTIME_AND_RESEARCH.md) and [Persistence](PERSISTENCE.md).
