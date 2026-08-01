# Research-First Rebuild Progress

**Status as of:** 2026-08-01
**Approved scope:** Phases 0-7, ending at the research quality gate
**Current status:** Phase 7 technical gate passed; representative-output review and user approval remain open
**Excluded:** Phase 8 tiering and Phase 9 theory/final cutover

## V2 codemap and cleanup initiative

**Status as of 2026-08-01:** Cleanup has begun as a separate, staged maintenance initiative. Its purpose is to establish an accurate V2 codemap and remove repository residue without changing the approved research-first scope or bypassing the Phase 7 stop gate.

1. **Hygiene artifacts — in progress.** Remove generated runtime files, local secrets, database sidecars, logs, snapshots, model binaries, obsolete worktree pointers, and other non-source artifacts from version control; retain only intentionally versioned fixtures and operational templates.
2. **Documentation truth pass — next.** Reconcile the README, documentation index, rebuild records, and the new codemap with the repository's actual V2 entry points, runtime behavior, test commands, supported routes, and current stop gate. Remove or clearly label stale claims.
3. **Dependency-verified legacy and template pruning — last.** Inventory old modules, templates, routes, API surfaces, and duplicate documentation; trace imports, router registration, template references, tests, scripts, and runtime dependencies before deleting anything. Prune only items proven unused, and preserve or replace any live dependency first.

**Cleanup decision rule:** Do not combine these stages or treat an apparent stale file as removable without dependency verification. Any discovery that changes V2 behavior, expands scope, or affects the Phase 7 acceptance gate requires separate review and authorization.

## Phase status

The sequence follows [07-implementation-plan.md](07-implementation-plan.md).

| Phase | Status | Acceptance evidence |
|---|---|---|
| 0. Approval and baseline freeze | **COMPLETE** | The user approved the documentation, clean-start policy, and implementation through Phase 7. |
| 1. Domain and contract baseline | **COMPLETE** | V2 contracts cover scoped research, evidence-linked material claims, run outcomes, providers, errors, and research projections. Contract and boundary tests pass. |
| 2. Clean test harness | **COMPLETE** | `backend/tests_v2` uses isolated temporary storage, denies external network access by default, supplies deterministic adapters, and separates default, evaluation, UI, slow, and network selections. |
| 3. Research domain and persistence foundation | **COMPLETE** | Schema, repository, immutability, rollback, seed, backup, concurrency, and graph integrity tests pass. A live clean bootstrap imported all 1,259 worlds. |
| 4. Durable run kernel | **COMPLETE** | Transition, lease, checkpoint, cancellation, bounded retry, durable target-level partial outcomes, multi-target, idempotency, and crash/restart evaluations pass without duplicate effects. Recoverable typed provider, structured-agent, and semantic-plan failures become durable gaps after transient retries are exhausted; unknown runtime and invariant failures remain terminal. |
| 5. Provider router, bounded context, and acquisition | **COMPLETE** | Production-adapter payload and error evaluations, routing, redaction, acquisition safety, deterministic targeted source preprocessing, MiniCPM fallback safety, browser fallback, bounded context, and fail-closed overflow tests pass. |
| 6. Research and verification pipeline | **COMPLETE** | The domain-free objective and targeting-hint flow is complete. Deterministic evaluations cover question-based completion, evidence-linked promotion, negative cases, contradictions, partial outcomes, repeat research, provenance, inheritance, exotic mechanisms, and branch isolation. |
| 7. Research UI and quality hardening | **TECHNICAL GATE PASSED; USER APPROVAL PENDING** | Automated UI tests and a real Chrome smoke pass. DB-configurable server and agent JSONL logging, diagnostics APIs, and the Settings Logs UI are complete. The remaining gate item is explicit user review and approval of representative research outputs. |
| 8. Dynamic tiering | **DEFERRED / NOT AUTHORIZED** | Blocked pending completion of the Phase 7 user gate and a separate go/no-go decision. |
| 9. Theory and final cutover | **DEFERRED / NOT AUTHORIZED** | Blocked pending research acceptance and later explicit authorization. |

## Current feature increment

Completed through 2026-08-01:

- Research runs now accept an optional global objective plus bounded keywords, exact phrases, and section hints shared by every selected world. Blank objectives start general research. Public planner, evidence, completion, projection, and gap behavior no longer depends on a fixed domain taxonomy; completion requires provenance-backed resolution of each planned question.
- Acquisition now performs deterministic search-title and snippet normalization, source cleanup, stable passage location, and targeted selection before MiniCPM processing. Unsupported HTML/wiki text and XHTML wrapper text remain intact. Explicit hints never broaden after a miss. Selected deterministic passages remain authoritative; rewrites with lexical omissions or additions are rejected in favor of that fallback, as are timeout, network/server/client, malformed-output, oversized-output, and grounding failures.
- `CachedFallbackSearch` now randomizes the provider order among DuckDuckGo, Google, Bing, and free Brave Search on each cache miss, caches successful `(query, limit)` results in a process-local bounded TTL/LRU cache (300 seconds and 256 entries by default), and never caches failures. Only after every free provider fails does it attempt the optional Brave Search API; that provider is unavailable unless its credential has been written through General Settings, where the credential remains write-only.
- `BrowserAcquisition` now keeps one lazy, profile-backed persistent browser context for the runtime and closes each request page after use; request interception and URL policy validation remain active for every browser request. The persisted browser state is constrained by browser origin rules—cookies, local storage, and similar state are available only to their originating site—and the configurable profile directory is secret-bearing operational data (`backend/data/v2-secrets/browser-profile` by default), not material to commit, expose, or export. Search diagnostics are typed and redact sensitive values before persistence or display.
- V2Runtime owns configurable SSH startup and shutdown for enabled local models. MiniCPM5-1B Q8_0 runs one 120,064-token slot at `http://192.168.1.30:8080` with `TEMP=0` / `TOP_K=1`; Qwen3.5-4B IQ4_XS runs with 81,920 context at `http://192.168.1.30:8081`. Environment-specific SSH paths and credentials, plus ownership of ports 8080 and 8081, remain operational constraints.
- Alembic migration `v2_0006_provider_route_targets` adds provider-level route targets, requires each route candidate to reference exactly one provider or model, and removes candidate weights. Routing follows strict candidate position order, and provider targets expand at call time to active models compatible with the step requirements.
- Research steps inherit the active `DEFAULT` route unless an explicit step route exists. Initialization cleanup removed six generated Qwen-only step overrides while preserving operator-defined explicit routes. Fresh databases and empty route configurations install the local Qwen provider, model, credential, and provider-level `DEFAULT` candidate.
- After an integrity-checked online backup, the live 373-entry `DEFAULT` chain was consolidated by first provider appearance into three provider targets: `google`, `main`, then `qwen-local`. This preserves provider precedence while allowing each target to resolve active compatible models dynamically.
- Settings now supports destructive resets for providers, models, routes, notebook data, knowledge data, and worlds. Notebook, knowledge, and world resets return HTTP 409 while research runs are active. Provider, model, and route resets restore the baseline local Qwen configuration; world resets reimport the configured seed.
- Model deletion accepts IDs containing slashes and removes associated explicit route candidates. Provider and credential guidance now explains stable IDs, endpoint configuration, write-only credentials, credential selection weights, model synchronization requirements, and provider-target expansion.
- The Models tab provides a provider-scoped **Fetch and prune models** action. Catalog IDs remain authoritative for persistence and probing; display labels remain presentation-only.
- `OpenRouterAdapter` authenticates requests to [`/api/v1/models/user`](https://openrouter.ai/docs/api/api-reference/models/list-models-filtered-by-user-provider-preferences-privacy-settings-and-guardrails). It excludes non-text output modalities and reconciles stale rows against the authoritative catalog already filtered by provider preferences, privacy settings, and guardrails.
- OpenRouter routing-layer errors may omit `error.metadata.error_type`. Pruning first requires a 4xx `INPUT` or `CAPABILITY` error. Typed errors qualify only for `not_found`, `invalid_request`, or `unprocessable`; untyped errors qualify only at HTTP 400 or 404. `AUTH` 401/403, payment 402, timeout 408, rate-limit 429, `CONTEXT`, `TRANSIENT`/5xx/network, and `INTERNAL` errors retain the model. Production code performs no message, model-ID, or provider-name matching.
- HTTP-200 embedded errors are detected. Every catalog model is probed independently, failures retain or delete only that model, and reports associate each reason with its own model. Deletion also removes explicit route candidates and `CandidateHealth` records while preserving provider-level route slots.
- Runtime logging now writes separate rotating `server.jsonl` and `agent.jsonl` streams. The database stores enablement, folder, independent levels, size limits, and backup counts; changes apply immediately. The Settings Logs tab and `/api/v2` diagnostics provide filtered, newest-first, escaped pagination while redaction, event bounds, file permissions, and path containment protect output.
- Duplicate provider-model names within one provider now return a sanitized HTTP 409 from REST and HTMX. A shared upsert performs a precheck and catches database races without exposing raw `IntegrityError` details.
- Each request receives a validated or generated `X-Request-ID`. Responses and request-scoped events inherit it. The server logs 4xx responses at WARNING and 5xx or unhandled failures at ERROR. Unhandled metadata includes the exception class and bounded application-only frames, without raw exception text.
- Browser JavaScript errors, rejected promises, and HTMX response or transport errors use the strict, bounded `/api/v2/logs/client-errors` endpoint. Best-effort client telemetry deduplicates reports and caps them at 20 per page; the server redacts accepted fields.
- Alembic migration `v2_0003_runtime_logging` adds `runtime_setting` and seeds enabled logging defaults while preserving upgrade from `v2_0002_freshness_scope`.
- Alembic migration `v2_0004_acquisition_cache_derivatives` isolates request-specific targeted derivatives from raw source-revision identity so different research hints cannot reuse unrelated passages.
- Alembic migration `v2_0005_question_scoped_leads` scopes lead identity to workspace, planned question, and canonical URL, preserving the same source as a distinct lead for each question. Extraction replay keys also include question identity, preventing cross-question evidence attribution.
- Alembic migration `v2_0006_provider_route_targets` preserves existing ordered model candidates while adding exclusive provider targets and removing unused route weights.
- Final review hardening ties completion to accepted evidence fragments for each planned question, applies preprocessor Settings changes to every live consumer, escapes remote SSH output, removes SSH passwords from process arguments, enforces one overall scout preprocessing deadline, and streams diagnostics without loading every rotated log into memory.
- Typed provider, structured-agent, and semantic-plan failures now preserve a durable target-level `PARTIAL` outcome and inspectable gap once bounded transient retries are exhausted. The affected target's remaining work is cancelled without affecting other targets. Unknown runtime failures and violated invariants remain terminal failures rather than being downgraded. Coverage includes provider and invalid semantic-plan partial-gap workflow evaluations and durable kernel partial-checkpoint coverage in `backend/tests_v2/test_evidence_workflow.py` and `backend/tests_v2/test_run_kernel.py`.

## Validation record

Final validation completed on 2026-07-30:

- Default suite: **266 passed, 28 deselected**.
- Evaluation suite: **294 passed**.
- UI suite: **32 passed**.
- Ruff lint: **passed**.
- `git diff --check`: **passed**.
- Coverage confirms optional domain-free objectives and hints, deterministic no-broadening passage selection, request-specific derivative caching, question-scoped leads and extraction replay, per-question accepted-evidence completion, authoritative-evidence enforcement, provider-model conflict handling, catalog-ID persistence, authenticated OpenRouter `/api/v1/models/user` discovery, authoritative stale-row reconciliation, non-text exclusion, metadata-first pruning with an untyped 400/404 fallback and no production message or model-ID matching, HTTP-200 embedded-error detection, independent model probing with model-local reasons, transactional route-candidate and health cleanup, request correlation, bounded client-error reporting, live Settings reconfiguration, separate JSONL streams, streamed diagnostics, `v2_0006` upgrade/downgrade/re-upgrade behavior, exclusive provider/model route targets, dynamic provider expansion, strict positional fallback, `DEFAULT` inheritance, explicit-route preservation, slash-safe model deletion, dependency-safe destructive resets, active-run reset conflicts, and baseline Qwen restoration. The HTTP-emulated OpenRouter test covers untyped 400/404 and typed 422 deletion; 401/402/403/408/429/503, network, content-policy, and HTTP-200 embedded 502 retention; successful continuation; authoritative stale removal; non-text filtering; and model-local reasons.
- Real Chrome smoke: **passed**. It verified default-enabled MiniCPM health, disable/enable runtime reconfiguration, Settings Logs configuration, and populated Server and Agent viewers. A live MiniCPM request reached `192.168.1.30:8080`; an oversized rewrite was rejected and the authoritative text fallback was retained.
- Live Models-tab rendering passed. After an integrity-checked backup, the live database was repaired for 13 `google` rows and 353 `main` rows. The repair preserved `qwen-local`'s intentional file-path `model_name` and the provider `DEFAULT` order.
- The live `openai/gpt-4o-mini` and `poolside/laguna-s-2.1` rows were removed through the route-safe deletion endpoint. `poolside/laguna-s-2.1:free` was preserved as unvalidated. SQLite integrity remained clean, and all three provider-level `DEFAULT` route slots remain intact.
- A live run exposed OpenRouter routing-layer errors without `error.metadata.error_type`. The reported batch-only row remains pending validation; the full live **Fetch and prune models** action was not rerun after adding the generic fallback because it can incur provider costs and reconcile stale or unsupported models.
- Live hardening smoke: a duplicate Qwen-name probe returned HTTP 409 with request ID `live-conflict-smoke` and inserted zero rows. A browser error report returned HTTP 204, and the resulting `client.event` entry redacted a bearer secret.
- Live lifecycle smoke: both `:8080` and `:8081` returned HTTP 200 after startup and were unreachable after shutdown. This smoke made health requests only. A prior separate concurrent-generation smoke established that both models generated successfully; neither smoke was a live research run.

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

No hosted external-provider API keys were configured; a local Qwen credential exists. Validation therefore made no live Gemini, OpenAI, or other hosted-provider calls. Deterministic evaluations exercised the production adapters, routing behavior, structured outputs, failure classes, and research workflow. The local-model lifecycle and generation smokes do not establish research quality, no live research run is claimed, and user review of representative outputs remains open.

## Residual gate

The technical gate has passed. The full Phase 7 research quality gate remains open until the user reviews representative outputs and gives explicit approval. A technical pass does not authorize later phases.

## Explicit stop gate

**STOP after Phase 7. Do not begin Phase 8 tiering, Phase 9 theory, or any tier/theory schema, API, workflow, UI, or test implementation under the current approval.**

After the user approves representative research quality, stop and request a separate go/no-go decision for Phase 8. Until then, return any failed review item to Phases 5-7. Do not infer authorization for tiering, theory, or final cutover from the technical validation results.
