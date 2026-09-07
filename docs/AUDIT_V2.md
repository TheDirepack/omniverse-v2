# V2 Audit and Validation

## Scope and outcome

Audited the deployed runtime in `backend/app/v2/` against its goal: turn scoped
fictional-universe research into accepted, evidence-backed canon with retrievable
provenance. Retained V1 code and deferred theory/tiering features were out of scope.

The original offline selection passed 321 tests and Ruff, but targeted failure
injection exposed defects that those tests did not cover. The prior fixes in commit
`8108d1e` have regression coverage; that validation passed **376 tests**, with five
live-network tests deselected. Ruff and `git diff --check` also passed at that stage.
Latest full continuation validation passed **381 tests**, with five live tests
deselected, in **42.86 seconds**. `./lint.sh` and `git diff --check` passed.

This establishes deterministic functional coverage, not live deployment readiness.

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

Implementation: `backend/app/v2/workflow.py`, `backend/app/v2/research_runs.py`,
`backend/app/v2/worker.py`, `test.sh`, `backend/pytest-v2.ini`, and
`backend/tests_v2/conftest.py`.

Regressions: `backend/tests_v2/test_evidence_workflow.py`,
`backend/tests_v2/test_run_kernel.py`, `backend/tests_v2/test_boundaries.py`,
`backend/tests_v2/test_runtime_composition.py`,
`backend/tests_v2/test_worker_research.py`, and
`backend/tests_v2/ui/test_commands.py`.

## Goal-level proof

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

## Verification

Run from the repository root:

```sh
./test.sh --evaluation -q
./lint.sh
git diff --check
```

The evaluation command includes deterministic evaluation and slow tests while
excluding live/network tests. No live app, real provider, or SSH process was
launched, and no production database reset or deployment operation was performed.
This does not imply earlier artifact isolation: tests could append to the
repository pipeline-debug file as noted above. Existing user changes, including
preprocessing and reconstruction documentation, were preserved.

## Remaining risks

- Actual live configuration and credentials, endpoint reachability, configured
  fallback availability, and source-site access were not tested. `from_env`
  enables remote model lifecycle by default; preprocessing can still issue an
  HTTP health probe when remote lifecycle is disabled.
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

The next validation stage is an explicitly authorized live research run with
bounded cost and a separate test data directory, followed by inspection of its
accepted canon, exact provenance, completion status, and correlated logs.
