# Omniverse V2 Rebuild Plan

**Status:** PROPOSED, planning only
**Decision owner:** user
**Implementation authorization:** NOT GRANTED

## Overview

This set records the source-backed current state and a recommended rebuild design. It is the approval baseline for implementation; it does not authorize code, schema, test, configuration, or data changes.

## Navigation

| Document | Purpose | Status |
|---|---|---|
| [01-current-system.md](01-current-system.md) | Reconstruct runtime behavior, persistence, views, tests, and defects | REVIEWED FROM SOURCE |
| [02-requirements.md](02-requirements.md) | Define actors, requirements, constraints, and acceptance criteria | PROPOSED |
| [03-target-architecture.md](03-target-architecture.md) | Specify one target architecture and its contracts | PROPOSED |
| [04-agent-runtime.md](04-agent-runtime.md) | Specify agent, routing, tool, and context behavior | PROPOSED |
| [05-research-system.md](05-research-system.md) | Specify acquisition, extraction, verification, promotion, and research quality | PROPOSED, PRIMARY DELIVERY TARGET |
| [06-tiering-and-theory.md](06-tiering-and-theory.md) | Specify deterministic tiering and non-canon theory handling | DEFERRED UNTIL RESEARCH ACCEPTANCE |
| [07-implementation-plan.md](07-implementation-plan.md) | Sequence test-first delivery and clean cutover | BLOCKED ON APPROVAL |

## Executive recommendation

Rebuild around one authoritative SQLite database, durable application-owned run state, typed domain artifacts, and a projection layer for Jinja/HTMX. Retain Python 3.12+, FastAPI, Jinja, HTMX, and the useful presentation shell. Replace the current five-database split, process-local orchestration state, polymorphic artifact payloads, and graph-controlled lifecycle.

Research is the first product milestone and the prerequisite for every later domain feature. Source acquisition, extraction, claim verification, contradiction handling, provenance, deduplication, and bounded-context efficiency must pass the research acceptance gate before tiering or theory implementation starts.

Use LangGraph only inside bounded reasoning steps if it provides value. It must not own run transitions or recovery. Route model calls through typed provider adapters and rebuild each prompt from a durable context manifest.

## Scope

- Reconstruct active behavior from source.
- Define target requirements, architecture, agent runtime, research/verification, tiering, and theory semantics.
- Plan a clean database bootstrap from `backend/app/db/default_worlds.json` and adapt the retained presentation.
- Define acceptance gates and rollback points.

## Non-goals

- Implement application, schema, or seed code.
- Modify current tests, configuration, documentation, or databases.
- Preserve `/api/v1` compatibility.
- Migrate any current database, run, provider, credential, notebook, artifact, rubric, classification, or theory record.
- Produce a full OpenAPI document or final visual redesign.
- Add multi-user authorization, distributed deployment, HATEOAS, or local rate-limit boilerplate.

## Key decisions

| ID | Decision | Status |
|---|---|---|
| D-01 | Keep FastAPI, Jinja, HTMX; require Python 3.12+ | PROPOSED |
| D-02 | Use SQLAlchemy 2.x, Alembic, Pydantic contracts, and one SQLite database in WAL mode | PROPOSED |
| D-03 | Store disposable raw/cache blobs outside the database by content hash | PROPOSED |
| D-04 | Make the application state machine authoritative; checkpoint every step | PROPOSED |
| D-05 | Separate typed canon artifacts from theories at the domain and storage layers | PROPOSED |
| D-06 | Version resource APIs under `/api/v2`; keep HTML routes unversioned | PROPOSED |
| D-07 | Treat 40k tokens as a baseline capability, not a maximum | PROPOSED |
| D-08 | Preserve presentation selectively; replace broken behavior behind retained pages | PROPOSED |
| D-09 | Store credential references in the database; use a local restricted secret file by default | PROPOSED |
| D-10 | Make tier content versioned and amendable while keeping assignment procedure deterministic | PROPOSED |
| D-11 | Start with a fresh database seeded only from `backend/app/db/default_worlds.json` | USER DIRECTED |
| D-12 | Complete and stabilize research before implementing tiering or theory | USER DIRECTED |

## Approval and stop gate

Implementation may start only when the user explicitly approves this documentation set and resolves all decisions marked **BLOCKING**. Approval should name the accepted document revision or commit.

Stop and return to planning if implementation discovery would change any of these boundaries:

- authoritative database or workflow ownership;
- canon/theory separation;
- context overflow behavior;
- credential storage default;
- deterministic tier assignment procedure;
- research evidence and verification guarantees.

Approval authorizes Phase 0 only. Each later phase requires its acceptance gate in [07-implementation-plan.md](07-implementation-plan.md).

## Next steps

1. Review open decisions in [02-requirements.md](02-requirements.md).
2. Approve, amend, or reject D-01 through D-10.
3. Record explicit authorization before any implementation work.
