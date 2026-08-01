# Omniverse V2 Autonomous Research Validation Loop

Use this prompt to operate the research pipeline as a continuing validation and repair loop. It is for an agent that can inspect code, run the application, execute tests, make scoped fixes, and retain a findings backlog.

````text
You own the Omniverse V2 research-validation loop. Continue through this loop:

  establish baseline → run research → inspect results and logs → reproduce
  findings → test first → fix → validate → rerun affected baselines → repeat

Do not end the loop because a pass count, report, or checklist is complete. Keep
working while reproducible defects, quality problems, efficiency waste,
observability gaps, or unvalidated fixes remain. A final report records the
current state; it does not end the loop.

Repository and required commands

- Repository root: `/home/max/Projects/omniverse-v2`
- Backend: `/home/max/Projects/omniverse-v2/backend`
- Start the runtime from the repository root:

  ```sh
  ./run.sh --prod > /tmp/opencode/omniverse-v2-research-loop.log 2>&1 &
  ```

- Run the targeted test for the change first, then use these exact commands as
  applicable:

  ```sh
  ./test.sh
  ./test.sh --ui
  ./test.sh --slow
  ./lint.sh
  ./lint.sh --strict
  ```

- Direct runtime logs, which you must inspect rather than infer from UI state:
  - `backend/logs/agent.jsonl`
  - `backend/logs/server.jsonl`
  - `backend/logs/remote-server.jsonl`
  - `/tmp/opencode/omniverse-v2-research-loop.log`
- Test logs: `backend/tests/logs/run_<timestamp>/`
- Useful views: `/validation` and `/logs/`

Runtime and endpoint discipline

1. Before each research batch, verify the server has started and the research,
   validation, logs, and relevant API endpoints respond through their intended
   lifecycle. Inspect the implemented routes instead of inventing an endpoint.
2. Exercise the normal UI/API workflow. Do not bypass lifecycle, acceptance,
   provenance, storage, or validation code with direct database writes.
3. Restart the runtime whenever a changed component, configuration, worker,
   connection, route registration, or stale process requires it. After a
   restart, verify endpoint availability and inspect all four direct log paths.
4. Record every terminal research run, including successful, failed, cancelled,
   and aborted runs. Record its run ID, world ID, input shape, status, provider
   and model attempts, accepted and rejected evidence, claims, persisted
   artifacts, endpoint checks, timestamps, and log file locations.
5. Preserve unrelated work. Never add fixture-name branches, prompt exceptions,
   or test-only behavior to production logic.

Fixed broad baseline fixtures

Use these exact baseline fixtures:

| World | World ID |
| --- | --- |
| Fallout: New Vegas | `fallout_nv` |
| A Song of Ice and Fire / Game of Thrones | `a_song_of_ice_and_fire_game_of_thrones` |

They are broad regression fixtures. Research each selected world with no
objective, keywords, phrases, section hints, or equivalent narrowing input.
Use its intended canonical continuity. Do not substitute a franchise-relative
continuity, adaptation, crossover, or related world. The fixture names and IDs
must never drive special-case logic.

For every fresh baseline, reset the Worlds DB using the project-approved reset
path. Record the exact reset/seed action, configuration, commit, command, and
timestamp. Never use manual database edits to hide a symptom.

Baseline protocol

Run the following pair until it has no significant reproducible defect:

1. **Fallout fresh/continuity pair.** Reset the Worlds DB. Run `fallout_nv`
   using broad selected-world research. Inspect persisted canon, provenance,
   validation state, notebook/workspace state, UI results, endpoint behavior,
   and direct logs. Without resetting data or changing inputs/provider
   configuration, run `fallout_nv` again and compare continuity behavior.
2. **ASOIAF fresh/continuity pair.** Reset the Worlds DB again. Run
   `a_song_of_ice_and_fire_game_of_thrones` using the same broad input shape.
   Inspect the same artifacts. Without resetting data or changing inputs/provider
   configuration, run ASOIAF again and compare continuity behavior.
3. Compare each fixture's fresh/continuity pair for idempotency, duplicate
   material, stale state, source and claim drift, cache behavior,
   cross-continuity leakage, provenance links, and persistence correctness.
4. Treat an unexplained difference as a defect until you identify and validate
   an intended nondeterministic boundary.
5. When you fix a finding, rerun the affected fixture. Rerun both complete
   fresh and unchanged-continuity fixture pairs before declaring baselines healthy.

Evidence and context boundary

Keep these data classes separate in code, prompts, reports, and validation:

- **Verified accepted canon context** (`accepted_canon_context`): bounded,
  database-persisted, accepted content with scoped provenance that resolves to
  supporting evidence. Only this class may support a canon claim, validation
  result, completion decision, or evidence-backed statement.
- **Unverified research context** (`unverified_research_context`): explicitly
  labelled notebook/workspace leads, extraction candidates, gaps, questions,
  and proposals. It may guide research planning only. It is not evidence and
  cannot become canon, validate a claim, or be represented as verified.

Continuity planning must consume bounded `accepted_canon_context` and the
explicitly labelled `unverified_research_context`. Ensure planning does not
treat workspace content as evidence, merge the classes, or permit unverified
material to enter canon without the normal acceptance and provenance path.

Provider, acquisition, and cache checks

1. Exercise normal routing and verify provider lifecycle, health, request,
   response, failure, and fallback events in persisted state and logs.
2. Qwen is the normal final-provider fallback. Verify that routing reaches it
   when the configured chain requires a final fallback and records the reason.
3. MiniCPM is for fetch/readability work only. Use it only with an
   authoritative fallback path. It must not become final research authority or
   silently replace the final-provider route.
4. Inspect search, acquisition, readability, extraction, cache hit/miss,
   invalidation, duplicate work, retry, timeout, provider fallback, and source
   attribution behavior. Verify retries have a reason and avoid repeating
   successful or permanently failing work without new input.

Log-led analysis and backlog

For every terminal run, analyze all four direct log paths. Correlate their
events with persisted run state, sources, artifacts, claims, provenance, and
the displayed UI. Do not limit analysis to error events.

Find and backlog every reproducible symptom in these categories:

- **BUG:** correctness, crashes, lifecycle, endpoint, routing, search,
  acquisition, cache, MiniCPM, provider fallback, storage, persistence, schema,
  cross-world, or continuity defects.
- **QUALITY:** source relevance and authority, evidence acceptance, claim
  support, scope, canon correctness, provenance, duplication, hallucinated
  certainty, and canon/notebook boundary leaks.
- **EFFICIENCY:** unnecessary calls, retries, fallback attempts, duplicate
  acquisition, extraction, cache misses, stale cache use, slow paths, and
  avoidable work.
- **OBSERVABILITY:** missing or misleading correlation, run/world/model/source
  attribution, lifecycle events, error reasons, terminal status, structured
  fields, log coverage, or reconstruction ability.
- **CONFUSION/REDUNDANCY:** ambiguous UI or workflow state, conflicting labels,
  repeated content, redundant prompts or requests, and behavior that makes the
  pipeline difficult to operate correctly.

Each backlog entry must include: category, severity and impact, exact
reproduction steps, affected run IDs, direct log path and line/event references,
frequency, observed and expected behavior, evidence, likely root cause, smallest
safe remediation, test plan, validation status, and any dependency. Retain
remaining findings in the backlog. Implement independent high-impact fixes
together when their tests and validation do not interfere.

Repair and validation rules

1. Reproduce each significant defect before changing production code. Write a
   focused failing test first. Do not change production code before the failure
   demonstrates the defect.
2. Make the smallest safe, general fix. A baseline fixture may expose a defect;
   it may not determine production behavior.
3. Run the focused test after the fix. Then run `./test.sh` and `./lint.sh`.
   Run `./test.sh --ui` for any HTMX, route, rendered state, or user workflow
   change. Run `./test.sh --slow` when the affected provider, acquisition, or
   network integration needs end-to-end verification. Run `./lint.sh --strict`
   when available for the changed code.
4. Restart the runtime where required, verify endpoints and lifecycle, and
   capture the direct logs for the rerun.
5. Validate fixes with affected runs and then the complete fresh and continuity
   baseline pairs. Unit tests alone never close a research-pipeline finding.
6. Keep a concise repair record: expected behavior, observed behavior, root
   cause, changed paths, test commands and results, rerun IDs, direct log
   evidence, and backlog disposition.

Hard blockers: ask before proceeding only for these

- Missing, expired, inaccessible, or unapproved credentials required to run the
  normal workflow.
- Unsafe or destructive ambiguity beyond the approved Worlds DB reset.
- A recurring failure that remains unfixable after disciplined diagnosis,
  reproduction, and safe remediation attempts.
- A security, privacy, legal, or policy ambiguity.

For a hard blocker, preserve evidence, state the exact decision needed, and ask
for it. Do not fabricate credentials or evidence, weaken safeguards, alter
unrelated data, suppress failures, or claim validation. All other failures are
inputs to diagnosis, repair, and another loop iteration.

Random-world final gate

Run this gate only after both baseline fresh-and-continuity pairs have no
significant reproducible defects. Select five worlds randomly from the eligible
world population, record the population query, selection method, seed, selected
IDs, and exclusions. Use the same broad selected-world input shape and the same
fresh/continuity discipline for each selection.

Analyze the random runs with the same provenance boundary, provider/acquisition,
cache, persistence, endpoint/lifecycle, and direct-log requirements. A
significant reproducible random-world failure returns the loop to diagnosis and
repair. After its fix, rerun and revalidate both baseline fresh-and-continuity
pairs before attempting the random-world gate again.

Status reporting

At each stable checkpoint, report baseline and random-gate status, terminal run
records, pair comparisons, direct log paths and evidence, findings backlog,
fixes, tests, lint, endpoint/lifecycle checks, remaining risks, and hard-blocker
questions. Mark a gate blocked whenever a required condition remains unmet.
````
