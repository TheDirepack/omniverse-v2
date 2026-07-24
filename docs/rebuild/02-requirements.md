# Omniverse V2 Rebuild Requirements

**Status:** PROPOSED
**Target user:** one local operator with technical familiarity

## Overview

The rebuild must first make research and evidence collection durable, efficient, verifiable, and inspectable. Tiering and theory depend on accepted research output and are deferred until the research acceptance gate passes. The system must support multiple providers, models, and keys while preserving the useful Jinja/HTMX presentation.

## Goals

| ID | Goal |
|---|---|
| G-01 | Produce typed, evidence-linked canon artifacts from recoverable research runs. |
| G-02 | Classify scoped subjects with a deterministic procedure and versioned rubric content. |
| G-03 | Keep theory separate from canon and expose its premises, assumptions, and falsifiers. |
| G-04 | Use 40k-context models safely and make productive use of larger windows. |
| G-05 | Support Gemini, OpenAI, and local OpenAI-compatible providers with multiple models and keys. |
| G-06 | Retain familiar presentation while replacing unreliable behavior and data contracts. |
| G-07 | Make research quality, provenance, and verification the primary release milestone. |

## Actors

| Actor | Goal |
|---|---|
| Local operator | Configure providers, manage worlds and profiles, start/stop/retry runs, inspect evidence, approve changes, and export data. |
| Workflow kernel | Execute durable state transitions, enforce budgets, checkpoint, and recover after restart. |
| Reasoning agent | Perform one bounded role with typed inputs, tools, and outputs. |
| Provider adapter | Normalize model discovery, capabilities, requests, usage, and errors. |
| Acquisition subsystem | Fetch, extract, hash, cache, and cite source material. |

## Functional requirements

### World, profile, and evidence

- **FR-001:** The operator can create and edit worlds, factions, civilizations, entities, and relationships.
- **FR-002:** A classification subject is a `PowerProfile` scoped by subject type, continuity, era, conditions, and baseline or peak mode.
- **FR-003:** Research stores immutable source revisions, compact evidence fragments, citations, and typed artifacts.
- **FR-004:** Canon promotion requires schema validation, evidence links, scope, confidence, and a recorded decision.
- **FR-005:** The system preserves artifact and evidence revision history.
- **FR-006:** The operator can inspect provenance from classification or artifact to exact evidence revision.
- **FR-007:** A research plan defines required capability domains, coverage questions, source priorities, stop conditions, and explicit unknowns before acquisition begins.
- **FR-008:** Verification distinguishes direct support, indirect support, contradiction, ambiguity, and unsupported model inference at claim-field granularity.
- **FR-009:** Research completion requires coverage and verification predicates; a summary alone cannot mark a target complete.

### Verified knowledge graph

- **FR-060:** The canon store represents concepts, mechanisms, models, concrete instances, specifications, capabilities, constraints, timeline events, and typed relationship assertions with stable identities and immutable revisions.
- **FR-061:** Reusable generic knowledge is referenced rather than copied. Multiple BattleTech mech models, for example, can implement the same fusion-engine mechanism revision while retaining model-specific engine and mech specifications.
- **FR-062:** The store distinguishes a reusable mechanism, a model or repeatable design, and a concrete instance. Instance deviations cannot mutate model or generic specifications.
- **FR-063:** Effective-knowledge queries combine applicable generic, model, and instance facts while preserving the scope, source revision, evidence, and identity of every assertion.
- **FR-064:** Relationship assertions are typed, revisioned, temporally scoped, and evidence-linked. Material edges require the same support, qualification, contradiction, and audit controls as material node fields.
- **FR-065:** Timeline events link participants and affected concepts, mechanisms, models, instances, specifications, capabilities, and relationships. Branching continuity and relative ordering are first-class.
- **FR-066:** Technological, magical, psychic, biological, dimensional, reality-altering, temporal, causal, conceptual, ontological, and hybrid mechanisms use the same canon verification rules.
- **FR-067:** Exotic mechanisms record evidenced effect, target, scale, activation, cost, duration, control, reliability, dependencies, limits, counters, and temporal/causal semantics without assigning a tier during research.
- **FR-068:** Research completion evaluates required relationship and timeline coverage, not only artifact-field coverage.
- **FR-069:** Hypothetical cross-setting mechanism compatibility exists only in theory and cannot appear as a canon relationship.

### Runs and agents

- **FR-010:** Research, tiering, theory, and maintenance commands create durable run resources.
- **FR-011:** Every step has an idempotency key, explicit state, attempt history, checkpoint, and terminal outcome.
- **FR-012:** Stop, retry, resume, and cancel survive process restart.
- **FR-013:** Partial world failure remains explicit and cannot mark failed work complete.
- **FR-014:** Agents exchange versioned Pydantic payloads, not free-form handoffs.
- **FR-015:** Tool calls record normalized input, status, timing, result reference, and error class.

### Providers and routing

- **FR-020:** The operator can configure multiple Gemini, OpenAI, and local OpenAI-compatible providers.
- **FR-021:** Each provider can have multiple write-only credentials and multiple discovered or manually configured models.
- **FR-022:** Routes select ordered candidates by task, capability, health, budget, and operator policy.
- **FR-023:** Key rotation and provider fallback avoid retrying permanent failures.
- **FR-024:** Capability checks include context window, tool calling, structured output, text output, and provider/model identity.
- **FR-025:** Provider and route reads never return secret values.

### Context

- **FR-030:** The effective context window equals `min(configured_cap, provider_model_window)` when a cap exists, otherwise the provider model window.
- **FR-031:** The runtime reserves output and tool margin before allocating input.
- **FR-032:** The 40k window is a baseline functionality target, not a maximum.
- **FR-033:** Larger windows receive larger evidence and working-memory budgets, but the runtime does not replay full transcripts automatically.
- **FR-034:** Each model call is rebuilt from a durable manifest containing goal, policy, summary, selected evidence, decisions, and recent tool events.
- **FR-035:** Raw tool output spills to content-addressed storage and appears in prompts only as compact extracts and IDs.
- **FR-036:** Overflow triggers deterministic compaction; unresolved overflow fails closed before a provider call.
- **FR-037:** The system stores decisions, citations, structured summaries, and tool events. It does not request or preserve hidden chain-of-thought.

### Tiering and theory

- **FR-040:** Tier content is versioned and amendable; tiering procedure is strict and deterministic.
- **FR-041:** Each classification stores overall tier, dimension vector, labels, confidence, evidence revisions, rubric version, and procedure version.
- **FR-042:** Rubric amendment runs classify impact and reclassify all affected profiles until a recorded no-change pass.
- **FR-043:** An iteration cap produces `NONCONVERGED`, never success.
- **FR-044:** Theory records premises, assumptions, compatibility, outcomes, confidence, evidence, and falsifiers.
- **FR-045:** Theory cannot satisfy canon evidence requirements or mutate canon without a separate promotion process.
- **FR-046:** Tiering and theory implementation cannot begin until the research quality gate in the implementation plan passes.

### API and HTML

- **FR-050:** JSON resources live under `/api/v2`; unversioned HTML routes render pages and HTMX fragments.
- **FR-051:** Collection APIs use one cursor-pagination envelope and stable sorting.
- **FR-052:** Errors use one envelope with code, message, details, and request ID.
- **FR-053:** Command endpoints accept an idempotency key and return the created or existing run.
- **FR-054:** HTMX fragments have named routes, documented target element, expected status codes, and trigger headers.

## Nonfunctional requirements

| ID | Requirement |
|---|---|
| NFR-001 | Python 3.12+; FastAPI, Jinja, and HTMX remain the application stack. |
| NFR-002 | SQLite uses WAL, foreign keys, busy timeout, bounded transactions, and one writer policy. |
| NFR-003 | A committed step and its durable outputs survive immediate process termination. |
| NFR-004 | Restart reconciliation resumes eligible runs or records a reasoned terminal state. |
| NFR-005 | Every persisted classification is reproducible from versioned procedure, rubric, profile, and evidence IDs. |
| NFR-006 | Logs redact credentials and avoid raw prompt/source bodies by default. |
| NFR-007 | Network access uses allowlisted schemes, blocks local/private targets by default, and enforces size/time limits. |
| NFR-008 | The clean test harness runs without external providers, browser downloads, or writes to checked-in data. |
| NFR-009 | Backup and restore use SQLite-safe mechanisms and include schema and blob-manifest versions. |
| NFR-010 | Core operations remain usable after provider failure; failed AI work remains inspectable and retryable. |

## Constraints

- The application is local and single-user. It does not need accounts, roles, distributed locks, or horizontal scaling.
- SQLite remains the authoritative database.
- The frontend remains server-rendered. No Node build step is introduced.
- Existing `/api/v1` clients may break after cutover.
- The target database starts empty and is seeded only from `backend/app/db/default_worlds.json`.
- No current database content, provider configuration, credential, run, artifact, notebook record, rubric, classification, or theory is migrated.
- Provider metadata can be incomplete or wrong; operator overrides require audit records.

## Assumptions

- One application process owns workflow scheduling and database writes.
- Parallel acquisition and provider calls are useful, but durable commits serialize through short transactions.
- Local filesystem permissions are available for the database, blob cache, and credential file.
- The operator accepts a practical local secret default rather than an operating-system keyring dependency.
- Existing visual structure has more value than existing route and persistence behavior.

## Acceptance criteria

| ID | Criterion |
|---|---|
| AC-01 | Kill and restart during each workflow phase; the run resumes or ends with a durable reason and no false completion. |
| AC-02 | A 40k model completes the reference research scenario without overflow or full transcript replay. |
| AC-03 | A larger-window model receives more selected evidence under policy, while old raw tool results remain out of the prompt. |
| AC-04 | Two providers, three models, and multiple keys route deterministically under simulated rate limit, auth, timeout, and capability failures. |
| AC-05 | Provider GET responses and HTML contain only key metadata and masked labels, never secret values. |
| AC-06 | A classification can be traced to exact profile, procedure, rubric, artifact, and evidence revisions. |
| AC-07 | A rubric amendment triggers impact analysis and a recorded no-change audit pass, or ends `NONCONVERGED`. |
| AC-08 | A theory cannot appear in canon queries and exposes assumptions and falsifiers in the UI. |
| AC-09 | A fresh installation creates the schema, imports the default-world registry idempotently, and contains no legacy runtime data. |
| AC-10 | Retained pages pass fragment-contract tests for normal, empty, validation-error, conflict, and failed-run states. |
| AC-11 | A representative world research run meets defined domain coverage, claim verification, contradiction, provenance, and deduplication thresholds. |
| AC-12 | Repeating research reuses unchanged sources and accepted evidence, targets known gaps, and does not duplicate canon artifacts. |
| AC-13 | Generic, model, instance, specification, timeline, and relationship queries preserve identity, applicability, temporal scope, and evidence provenance for technological and exotic mechanisms. |

## Open decisions

| ID | Decision | Status | Recommended default |
|---|---|---|---|
| O-01 | Credential file format and path | BLOCKING | JSON at `backend/data/secrets/credentials.json`, mode `0600`, atomic replace; DB stores opaque references. |
| O-02 | Default peak-profile policy | OPEN | Require a separate explicit peak profile; never infer peak from baseline. |
| O-03 | Local OpenAI-compatible structured-output fallback | OPEN | Use tool calling when verified; otherwise JSON schema prompt plus strict parse/repair with one retry. |
| O-04 | Blob retention | OPEN | Keep referenced blobs; apply size/age policy only to unreferenced cache objects. |

## Next steps

Resolve O-01 before provider configuration is implemented. O-02 through O-04 must be resolved before their dependent phases in [07-implementation-plan.md](07-implementation-plan.md).
