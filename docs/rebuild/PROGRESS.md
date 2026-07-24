# Research-First Rebuild Progress

**Status as of:** 2026-07-24
**Approved scope:** Phases 0-7, ending at the research quality gate
**Current status:** Phase 7 technical gate passed; representative-output review and user approval remain open
**Excluded:** Phase 8 tiering and Phase 9 theory/final cutover

## Phase status

The sequence follows [07-implementation-plan.md](07-implementation-plan.md).

| Phase | Status | Acceptance evidence |
|---|---|---|
| 0. Approval and baseline freeze | **COMPLETE** | The user approved the documentation, clean-start policy, and implementation through Phase 7. |
| 1. Domain and contract baseline | **COMPLETE** | V2 contracts cover scoped research, evidence-linked material claims, run outcomes, providers, errors, and research projections. Contract and boundary tests pass. |
| 2. Clean test harness | **COMPLETE** | `backend/tests_v2` uses isolated temporary storage, denies external network access by default, supplies deterministic adapters, and separates default, evaluation, UI, slow, and network selections. |
| 3. Research domain and persistence foundation | **COMPLETE** | Schema, repository, immutability, rollback, seed, backup, concurrency, and graph integrity tests pass. A live clean bootstrap imported all 1,259 worlds. |
| 4. Durable run kernel | **COMPLETE** | Transition, lease, checkpoint, cancellation, retry, multi-target, idempotency, and crash/restart evaluations pass without duplicate effects. |
| 5. Provider router, bounded context, and acquisition | **COMPLETE** | Production-adapter payload and error evaluations, routing, redaction, acquisition safety, browser fallback, 40k context, larger-window scaling, and fail-closed overflow tests pass. |
| 6. Research and verification pipeline | **COMPLETE** | Deterministic evaluations cover evidence-linked promotion, negative cases, contradictions, partial outcomes, repeat research, provenance, inheritance, exotic mechanisms, and branch isolation. |
| 7. Research UI and quality hardening | **TECHNICAL GATE PASSED; USER APPROVAL PENDING** | Automated UI tests and a real Chrome smoke pass. The remaining gate item is explicit user review and approval of representative research outputs. |
| 8. Dynamic tiering | **DEFERRED / NOT AUTHORIZED** | Blocked pending completion of the Phase 7 user gate and a separate go/no-go decision. |
| 9. Theory and final cutover | **DEFERRED / NOT AUTHORIZED** | Blocked pending research acceptance and later explicit authorization. |

## Validation record

Validation completed on 2026-07-24:

- Default suite: **145 passed, 28 deselected**.
- Evaluation suite: **173 passed**.
- UI suite: **21 passed**.
- Ruff lint and Ruff format checks: **passed**.
- Shell syntax checks with `bash -n`: **passed**.
- `git diff --check`: **passed**.
- Live clean bootstrap: **1,259 worlds imported** from `backend/app/db/default_worlds.json`.
- Live health endpoint: **passed**.
- Real Chrome smoke: the Research page loaded; creating a run replaced the queue fragment; searching for **BattleTech** filtered the world list through HTMX.
- Final review remediation confirms cancellation waits for every concurrent active lease boundary. Genuine evidence-gap `PARTIAL` runs can append a retry pass.
- Review regressions also cover expired-lease cancellation reconciliation, persisted accepted-proposal IDs in completion integrity checks, model-local ID collision scoping, fail-closed browser interception, backend-anchored relative config paths, corrected `app.v2` package discovery, Python >=3.10 checks for existing virtual environments, configured acquisition body limits, concurrent credential write serialization and failed-persist cleanup, and stable filtered log pagination.

Relevant automated evidence resides in `backend/tests_v2`, including contract and boundary tests, seed and persistence tests, the durable run kernel, provider and acquisition adapters, context budgets, research-gate correctness, evidence workflow evaluations, runtime composition, and UI journeys.

## Research acceptance gate

Technical validation covers items 1-12 in the 13-item gate defined by [05-research-system.md](05-research-system.md):

- [x] Fresh bootstrap and default-world import without legacy runtime data.
- [x] Deterministic fixture coverage for completion, partial results, contradictions, sparse evidence, and continuity or branch isolation.
- [x] Exact evidence and source-revision provenance for promoted material fields.
- [x] Rejection of unsupported, fabricated, snippet-only, and wrong-scope evidence.
- [x] Retention and scoping of contradictions, qualifiers, prototypes, inheritance, and timeline branches.
- [x] Restart, replay, idempotency, acquisition reuse, and duplicate-prevention coverage.
- [x] 40k and larger-window bounded-context evaluations without transcript replay.
- [x] Inspectable provider, browser, acquisition, malformed-output, budget, and overflow failures.
- [x] Research-facing projections and UI journeys, including Knowledge, Validation, Provenance, Flow, Logs, and Settings.
- [ ] **User reviews representative artifacts and provenance and approves research quality.**

No external-provider keys were configured. Validation therefore did not make live Gemini, OpenAI, or OpenAI-compatible model calls. Deterministic evaluations exercised the production adapters, routing behavior, structured outputs, failure classes, and research workflow. Live external-provider behavior remains unclaimed.

## Residual gate

The technical gate has passed. The full Phase 7 research quality gate remains open until the user reviews representative outputs and gives explicit approval. A technical pass does not authorize later phases.

## Explicit stop gate

**STOP after Phase 7. Do not begin Phase 8 tiering, Phase 9 theory, or any tier/theory schema, API, workflow, UI, or test implementation under the current approval.**

After the user approves representative research quality, stop and request a separate go/no-go decision for Phase 8. Until then, return any failed review item to Phases 5-7. Do not infer authorization for tiering, theory, or final cutover from the technical validation results.
