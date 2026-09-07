# 3. Data model and invariants

## Physical stores

| Store | Default location | Purpose |
|---|---|---|
| SQLite | `backend/data/omniverse-v2.db` | all relational state and JSON metadata |
| Blobs | `backend/data/v2-blobs/` | content-addressed source and derivative bytes |
| Credential file | `backend/data/v2-secrets/credentials.json` | secret values behind opaque database references |
| Browser profile | `backend/data/v2-secrets/browser-profile/` | browser session data |
| Settings file | `backend/data/ui_persistence.json` | UI-controlled environment-like settings |
| Logs | `backend/logs/*.jsonl` | server, agent, and remote-server events |

Blob keys are SHA-256 digests, laid out as `<root>/<first-two>/<next-two>/<digest>`.
Verify a digest when reusing or reading a blob. Secret directory/file modes are 0700/
0600; database rows hold `json:` or `env:NAME` references and metadata, never values.

## Schema groups

`models.py` is the authoritative SQLAlchemy schema. Alembic migrations in
`backend/alembic_v2/versions` establish baseline through `v2_0008` (provider model
ordering). Group the tables as follows when rebuilding:

| Group | Tables |
|---|---|
| Runtime/world seed | `runtime_setting`, `world`, `continuity`, `timeline_branch`, `subject`, `subject_relation`, `policy_definition`, `seed_run` |
| Sources/evidence | `source`, `source_revision`, `evidence_fragment`, `citation`, `acquisition_cache` |
| Workspace/wiki | `research_workspace`, `wiki_profile`, `wiki_inventory_page`, `wiki_page_queue`, `workspace_knowledge_publication`, `search_lead`, `coverage_record`, `research_gap` |
| Proposals/audit | `material_proposal`, `material_proposal_field`, `proposal_field_evidence`, `claim_conflict`, `audit_decision`, `promotion_decision`, `workflow_summary`, `structured_summary_revision` |
| Run kernel | `run`, `run_target`, `run_step`, `step_attempt`, `checkpoint`, `outbox_event`, `step_effect`, `model_step_effect`, `integration_effect`, `tool_event`, `context_manifest`, `model_call` |
| Provider configuration | `provider`, `provider_model`, `credential_ref`, `provider_route`, `provider_route_candidate`, `provider_candidate_health`, `provider_credential_health` |
| Canon graph | `canon_node`, `canon_node_revision`, `relationship_assertion`, `relationship_revision`, `node_evidence`, `relationship_evidence` |

Key links: a source owns immutable revisions; a fragment belongs to one revision;
citations and node/relationship evidence point to fragments. A run has targets and
ordered steps; a workspace binds run+target+scope. Proposals hold fields and field
evidence, audit decisions govern their promotion, and integration appends canon
revisions rather than mutating past truth. Provider routes have ordered candidates;
health is scoped to candidate or credential.

## Correctness guarantees

* Foreign keys are enabled; SQLite uses WAL and configurable busy timeout.
* `ResearchWorkspace` uses optimistic versioning; IDs are strings and most event IDs
  are generated with prefixed UUIDs.
* Source, evidence, canon, relationship, audit/promotion, model-call, manifest,
  effect, and summary revision records are append-only. Both SQLAlchemy flush guards
  and SQLite triggers reject mutation/deletion of protected records.
* Seed import validates unique IDs, parent existence, and parent cycles; startup also
  validates migration head, required schema, foreign keys, and imported seed hash.
* `database_resets` supports only providers, models, routes, notebook, knowledge, and
  worlds. Notebook/knowledge/world resets refuse active runs. Resets do not garbage
  collect blobs.

## Canon graph rules

Nodes and relationships have immutable revision history and scoped provenance.
Relationships such as taxonomy/instance inheritance are cycle-checked. Evidence can
support, contradict, or qualify an assertion; a lead-only role cannot support canon.
Promotion checks source policy, scope, exact source linkage, accepted audit outcome,
field completeness, contradiction state, and independent support as applicable.
These constraints make revisions auditable and reproducible even when models fail.
