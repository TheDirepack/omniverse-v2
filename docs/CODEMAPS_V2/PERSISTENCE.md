# Omniverse V2 Persistence

V2 stores state in one Alembic-managed SQLite database, content-addressed blobs, and a protected credential file.

## Default paths

| Store | Path |
|---|---|
| Database | `backend/data/omniverse-v2.db` |
| Blobs | `backend/data/v2-blobs/` |
| Credentials | `backend/data/v2-secrets/credentials.json` |
| Browser profile | `backend/data/v2-secrets/browser-profile/` |
| UI settings file | `backend/data/ui_persistence.json` |

`V2Config` supports `OMNIVERSE_V2_*` path overrides. `BlobStore` addresses data by SHA-256 at `<root>/<first-two>/<next-two>/<digest>` and verifies every existing/read blob. Raw source bytes, deterministic derivatives, and MiniCPM readability output are distinct blobs.

The database stores opaque credential references and metadata, never secret values. `JsonCredentialStore` supports stored `json:` references and `env:VARIABLE_NAME`; it writes secret directories as `0700` and files as `0600`.

## Schema and migration

`backend/alembic-v2.ini` configures `backend/alembic_v2/`. SQLite runs with foreign keys, WAL, and a configurable busy timeout. Startup requires all V2 tables/columns, Alembic head, passing foreign-key checks, and a matching imported seed.

The baseline migration creates immutable triggers for source/evidence/canon/relationship revisions, audit and promotion decisions, model calls, manifests, effects, and structured summaries.

| Domain | Examples |
|---|---|
| Configuration | providers, models, routes, credential references, runtime settings |
| Run kernel | runs, targets, steps, attempts, checkpoints, outbox events |
| Workspace | leads, gaps, proposals, audits, summaries, tool events |
| Provenance/canon | sources, revisions, fragments, nodes, relationships, citations |

`backend/app/v2/models.py` is the authoritative schema.

## Reset boundaries

The reset service supports `providers`, `models`, `routes`, `notebook`, `knowledge`, and `worlds`. Notebook, knowledge, and world resets refuse active runs. Provider resets remove non-environment secrets; world resets reimport the seed. Provider/model/route resets restore the Qwen development default.

The reset service does not garbage-collect blobs. Audit references before deleting blob data outside the service.

See [Operations](OPERATIONS.md).
