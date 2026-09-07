# Omniverse V2 reconstruction guide

This folder is the implementation guide for rebuilding the deployed application from
first principles. It documents the active V2 system, rather than the historical V1
code that remains in the repository.

## Read in this order

1. [System map](01-system-map.md) — repository layout, boundaries, and startup graph.
2. [Runtime and workflow](02-runtime-and-workflow.md) — durable research execution,
   acquisition, model routing, and evidence rules.
3. [Data model and invariants](03-data-model-and-invariants.md) — SQLite schema,
   blobs, credentials, migrations, and correctness constraints.
4. [Interfaces and operations](04-interfaces-and-operations.md) — HTTP/HTMX surfaces,
   configuration, local setup, and verification.
5. [Wiki research architecture improvements](05-wiki-research-improvements.md) — a
   roadmap for adapter-based, revision-aware, high-recall wiki research.

## Reconstruction target

Recreate a local-first fictional-universe research application that accepts a scoped
research request, acquires and preserves source material, extracts exact evidence,
uses structured model calls to create and audit provisional proposals, and promotes
only accepted evidence-backed results to a versioned canon graph. The application is
FastAPI + SQLAlchemy + SQLite + Jinja/HTMX. It is deliberately server-rendered: there
is no React client, build pipeline, or separate frontend service.

## Canonical source boundary

The running entry point is `backend/app/main.py`, which exposes the result of
`app.v2.main.create_app()`. All implementation paths below `backend/app/v2/` are
current runtime code. Directories such as `backend/app/api/`, `backend/app/views/`,
`backend/app/services/`, and `backend/app/workflow/` are retained V1 material and
must not be copied into a V2 reconstruction.

For source-level cross-checking, use `docs/CODEMAPS_V2/`. This guide adds the design
relationships and rebuild sequence that those concise codemaps intentionally omit.
