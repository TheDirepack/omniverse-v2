# V2 Audit and Validation

## Scope and outcome

Audited the deployed runtime in `backend/app/v2/` against its goal: turn scoped
fictional-universe research into accepted, evidence-backed canon with retrievable
provenance. Retained V1 code and deferred theory/tiering features were out of scope.

The original offline selection passed 321 tests and Ruff, but targeted failure
injection exposed defects that those tests did not cover. The prior fixes in commit
`8108d1e` have regression coverage; that validation passed **376 tests**, with five
live-network tests deselected. Ruff and `git diff --check` also passed at that stage.
An earlier full continuation validation passed **381 tests**, with five live tests
deselected, in **42.86 seconds**. `./lint.sh` and `git diff --check` passed.

The subsequent pre-gzip baseline was **383 tests**. The final full rerun after the
gzip changes passed **397 tests**, with five live tests deselected, in **38.13
seconds**. Ruff and `git diff --check` also passed.

Offline results establish deterministic functional coverage, not live deployment
readiness. The authorized live validation below did **not meet the goal**: no live
run reached COMPLETE with accepted evidence-backed canon and retrievable provenance.

## Findings and fixes

| Priority | Finding | Fix and regression evidence |
|---|---|---|
| High | INTEGRATE trusted audit acceptance without enforcing target scope and evidence support eligibility. Wrong-scope proposals or contradictory support could promote to canon. | Enforce target scope and field-level evidence eligibility at promotion. Invalid cases leave durable rejection gaps instead of canon. Normalize unordered conditions so equivalent scopes remain valid. |
| High | Crash replay validated persisted JSON as strict Python objects, rejecting JSON lists for tuple fields. | Validate persisted effects as JSON. Recovery tests require COMPLETE, exactly one canon integration, and no duplicate model calls across model-backed steps. |
| High | Manual retry could append work behind an exhausted failed step, leaving no leasable work; retry below the limit could append duplicate work. | Reopen failed steps for explicit manual retry, preserve attempt history, and avoid duplicate chains. Automatic retry limits remain bounded. Tests verify leasing, restart persistence, and terminal outcomes. |
| Medium | Replanning with new question IDs reused historical leads and crashed extraction with a missing-question lookup. | Restrict SCOUT's selected leads to current-plan questions while retaining historical records. A two-plan regression completes without stale extraction. |
| Medium | The test wrapper overrode pytest's live exclusion; slow/evaluation markers also disabled the network guard. | Exclude live/network tests in default, slow, and evaluation wrapper modes. Only explicit live/network markers permit external connections. Regression tests verify wrapper arguments and the guard without contacting endpoints. |
| High | Immediate worker shutdown could hang: scheduled `run()` cleared the stop event after `stop()` had set it. | Move `stop_event.clear()` into synchronous `start()` before scheduling. The immediate `worker.start(); await worker.stop()` regression timed out before the fix and now passes, including repeated start/stop cycles. |
| Medium | Earlier tests could append to hardcoded `backend/data/pipeline-debug.jsonl` even with a temporary database; UI persistence also needed isolation. | A global autouse fixture now isolates pipeline debug output and UI persistence for tests. Both path-isolation regressions failed against repository paths before the fixture and now pass in the full suite. Production diagnostics are unchanged. |
| Medium | Live acquisition rejected an `application/x-gzip` sitemap. | Added sitemap-only gzip support in `wiki.py`, retaining the 5 MB download cap and limiting expanded XML to 50 MB. DOCTYPE/entities remain forbidden. Corrupt-gzip and decompression-bomb tests pass in the final 397-test suite. |

Implementation: `backend/app/v2/workflow.py`, `backend/app/v2/research_runs.py`,
`backend/app/v2/worker.py`, `backend/app/v2/wiki.py`, `test.sh`, `backend/pytest-v2.ini`, and
`backend/tests_v2/conftest.py`.

Regressions: `backend/tests_v2/test_evidence_workflow.py`,
`backend/tests_v2/test_run_kernel.py`, `backend/tests_v2/test_boundaries.py`,
`backend/tests_v2/test_runtime_composition.py`,
`backend/tests_v2/test_worker_research.py`, `backend/tests_v2/test_wiki_research.py`, and
`backend/tests_v2/ui/test_commands.py`.

## Deterministic goal-level proof

A new default-selected HTTP integration test uses an isolated runtime with its
worker disabled and deterministic source, search, and model adapters. It verifies:

1. HTTP run creation and an idempotent repeat return the same run ID.
2. The workflow executes against that runtime's database.
3. HTTP run retrieval reports COMPLETE and SUCCEEDED.
4. Canon retrieval contains the accepted field.
5. Provenance connects the field to evidence and the expected source revision;
   the persisted source URL is verified.

The broader suite covers initialization/migration safety, provider fallback using
fakes, acquisition policy, evidence grounding, cancellation and recovery,
provenance, and HTTP/template UI behavior.

### Continuation: runtime-built worker proof

`backend/tests_v2/test_worker_research.py` exercises the actual runtime-built
workflow, router, provider adapter, and acquisition stack through the application
lifespan with a real background worker. External HTTP is mocked; search and DNS
are deterministic. API submission and polling verify:

- Healthy execution reaches COMPLETE/SUCCEEDED with five model requests.
- A first-provider HTTP 503 leaves durable PARTIAL state; API manual retry reaches
  COMPLETE with six model requests and preserved failed-attempt history.
- Both cases produce exactly one canon result with the expected field, exact
  excerpt, evidence/source revision links, source URL, and stored source bytes,
  without duplicate effects. Lifespan exit shuts down the worker gracefully.

## Historical offline verification

Run from the repository root:

```sh
./test.sh --evaluation -q
./lint.sh
git diff --check
```

The evaluation command includes deterministic evaluation and slow tests while
excluding live/network tests. During that offline phase, no live app, real
provider, or SSH process was launched, and no production database reset or
deployment operation was performed. These no-network statements apply only to
that phase, not to the subsequent authorized live validation.
This does not imply earlier artifact isolation: tests could append to the
repository pipeline-debug file as noted above. Existing user changes, including
preprocessing and reconstruction documentation, were preserved.

## Authorized live validation: 2026-09-07

### Scope, isolation, and delivery status

The user explicitly authorized production credential use and pushing all changes.
`main` was pushed through `093dd3c` to `origin/main`, including the user's
preprocessing chunk fix and six reconstruction documents. Raw debug output and
UI persistence are gitignored. This push milestone does not establish deployment
or validation success for the later gzip changes.

The live harness read production routing and credentials through a read-only
production database and an in-memory credential facade, then used an isolated
temporary database. It exercised the actual built runtime and background worker
through the API, with no source or model fixtures. It made no deployed-data writes
and used no SSH. Browser acquisition and preprocessing were disabled; their
availability remains unverified. The active model override described below applied
only to the isolated runtime; production routing did not change.

Each attempt was limited to 20 model HTTP requests, 4,096 output tokens per
request, 120 source requests, and less than 10 minutes. These were harness limits,
not proof of production-wide budget enforcement.

### Attempts and observed outcomes

| Attempt | Configuration and requests | Result |
|---|---|---|
| `run_514f69efc8014a88971afa3754bd39a4` | Default production priorities; 20 model HTTP requests, 6 source requests; 58.37 seconds. | Budget stop before terminal state. Many retired Google model endpoints returned 404, one request returned an API-version 400, and structured-output failures also occurred. Zero sources, evidence, or canon. Acquisition exposed the gzip sitemap rejection. |
| `run_1f93537a23ef47a8944be82b7a8fd816` | After sitemap gzip support; isolated active model pinned to `gemini-3.5-flash-lite`. Broad `fallout_nv`, `primary` continuity, blank objective, `max_gap_loops=0`; 3 model HTTP requests, 12 source HTTP requests, all source responses 200; 48.12 seconds. | All steps succeeded, but the research outcome was PARTIAL: 2 real source revisions, 0 evidence, 0 canon, and 1 gap. Step success did not establish goal completion. |
| `run_de39137a46694d3ca0f56511c257c45e` | New continuity run on the same isolated data; 1 provider request; 52.99 seconds. | PLAN failed after HTTP 503; outcome PARTIAL, with no additional sources. Live continuity completion remains unproven. |

The post-fix run acquired `https://fallout.wiki/wiki/$20_NCR` and
`https://fallout.wiki/wiki/$5_NCR`, unrelated to the planned NCR Heavy Trooper armor
research. The 500-page alphabetical inventory truncation and selection of the
first 12 passages, dominated by headers and infobox content, explain the relevance
and passage-coverage gap. The run promoted no unsupported canon, but also produced
no accepted evidence or canon.

Across the three attempts, the harness recorded **24 provider requests**, including
failed requests. No currency-cost or aggregate token-usage claim is made. Actual
Gemini credential use was validated; other providers' credentials were resolved
but not tested against their services. No further paid calls will be made in this
validation phase.

Local artifacts remain uncommitted under
`/tmp/opencode/omniverse-live-20260907-validation` and
`/tmp/opencode/omniverse-live-gzip-validation`. This audit records sanitized findings
only, without credential references or secret contents.

## Remaining risks

- **Outdated provider configuration:** live default priorities encountered retired
  models and an API-version incompatibility. Likelihood: high; impact: high;
  response: escalate. Review configured models and API versions before another
  default-routing validation. The isolated Gemini success does not validate the
  configured fallback chain or other providers.
- **Acquisition relevance and passage coverage:** the live run fetched unrelated
  pages and produced no evidence. Likelihood: high; impact: high; response:
  escalate. Address inventory truncation, question-to-source relevance, and
  passage selection before another paid goal-level run.
- **Provider availability:** the continuity attempt failed on HTTP 503.
  Likelihood: medium; impact: high; response: mitigate. Validate bounded recovery
  and fallback behavior; deterministic recovery proof is not live recovery proof.
- Browser and preprocessing availability remain unverified. `from_env` enables
  remote model lifecycle by default; preprocessing can still issue an HTTP health
  probe when remote lifecycle is disabled.
- There is no run-wide model-call or deadline budget. Test bounds do not establish
  production cost or duration limits.
- Production pipeline diagnostics remain unredacted in a fixed repository file
  with unbounded total growth. The new fixture isolates tests only.
- Deterministic fixtures do not establish research breadth, factual quality on
  arbitrary worlds, latency, or model-call cost.
- UI tests use TestClient, not a browser. Desktop/mobile rendering and HTMX
  execution still require browser validation.
- Already-stranded WAITING_RETRY records are not retroactively repaired by the
  retry fix. Inspect existing run state before attempting operational recovery;
  this audit did not mutate deployed records.
- This was a functional and evidence-integrity audit, not a comprehensive security,
  dependency, or performance audit.

## Dependencies and decisions needed

- **Current phase:** live validation stopped on 2026-09-07. The final offline
  regression rerun passed. No further paid calls are planned in this phase.
- **Critical path:** review outdated provider configuration and address acquisition relevance and passage coverage before
  considering another live attempt. No delivery estimate is established.
- **Production safety:** production credentials are authorized for testing, but the
  validation did not change production routing. Keep future experiments isolated
  and bounded while addressing the remaining blockers.
- **Go/no-go:** live goal acceptance is **NO-GO / NOT MET**. Acceptance requires a
  live COMPLETE outcome with accepted evidence-backed canon, exact retrievable
  source provenance, and inspected completion state and correlated logs. A PARTIAL
  run with successful steps and source downloads does not satisfy that gate.
