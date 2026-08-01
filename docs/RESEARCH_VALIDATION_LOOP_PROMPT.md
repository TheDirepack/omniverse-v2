# Omniverse V2 Research Validation and Development Loop

Use this prompt to run a bounded research-validation pass and make only evidence-backed fixes.

```text
You are validating the Omniverse V2 research pipeline. Work in a tight
research → inspect → diagnose → test → fix → re-run loop. Preserve unrelated
work and do not broaden the task.

Repository and commands
- Repository root: /home/max/Projects/omniverse-v2
- Backend: /home/max/Projects/omniverse-v2/backend
- Start local app: ./run.sh
- Default test suite: ./test.sh
- UI suite: ./test.sh --ui
- Lint: ./lint.sh
- Test logs: backend/tests/logs/run_<timestamp>/
- Runtime agent log: backend/data/logs/agents.log
- Validation views: /validation and /logs/

Fixed broad baselines
1. Fallout: New Vegas
2. A Song of Ice and Fire (ASOIAF)

Run these baselines first and keep their world, continuity, research question,
provider route, and run identifier fixed for the full validation cycle. Use
the intended canonical continuity for each baseline. Do not substitute a
related franchise, adaptation, or crossover continuity.

Cycle A: clean baseline
1. Start from the project-approved clean state. Record the exact reset or seed
   action, configuration, commit, command, and timestamp.
2. Run Fallout: New Vegas, then ASOIAF, through the normal research workflow.
3. Capture each run ID, status, sources, accepted evidence, claims, failures,
   provider/model attempts, elapsed time, and log locations.
4. Inspect the resulting canon, provenance, validation, and agent-log views.

Cycle B: continuity baseline
1. Without changing provider configuration or baseline inputs, repeat the same
   two runs against the persisted state.
2. Compare cycle results for duplicated material, stale state, cross-world or
   cross-continuity leakage, idempotency, provenance links, and output drift.
3. Treat unexplained differences as defects until evidence proves an intended
   nondeterministic boundary.

Notebook and canon boundary
- Notebook entries are leads, drafts, or unconfirmed extraction. They cannot
  satisfy a canon claim, validation result, completion condition, or quality
  metric.
- Canon claims require accepted, scoped evidence and working provenance.
- Reject or repair any case where notebook content becomes canon without the
  required acceptance and provenance path.

Log analysis
For every baseline run, analyze agents.log and test/run logs. Report findings
under all three headings:
- Quality: source relevance, evidence acceptance, claim support, scope and
  continuity correctness, provenance, duplication, and canon/notebook leaks.
- Efficiency: elapsed time, retries, failed calls, duplicate acquisition or
  extraction, unnecessary model fallbacks, and avoidable work.
- Observability: run correlation, world and model attribution, event coverage,
  useful failure reasons, log completeness, and ability to reconstruct the run.

Development rules
1. Reproduce a significant defect with a focused failing test before changing
   production code.
2. Make the smallest scoped fix. Run the focused test, then ./test.sh and
   ./lint.sh. Run ./test.sh --ui when the defect touches an HTMX workflow.
3. Re-run both fixed baselines after each fix. Do not call a fix complete from
   unit tests alone.
4. Record a concise defect report: expected behavior, observed behavior,
   evidence, root cause, changed paths, test command and result, and rerun IDs.

Hard blockers
- Stop before random-world validation if either fixed baseline has a significant
  quality, efficiency, observability, continuity, provenance, or
  notebook-to-canon defect.
- Stop if a run cannot be correlated across its persisted result and logs.
- Stop if canon relies on notebook-only material or lacks accepted provenance.
- Stop if tests, lint, migrations, configuration, or provider health prevent a
  trustworthy baseline run. Report the blocker; do not mask it with manual DB
  edits, fabricated evidence, or skipped checks.

Final gate
Only after both clean and continuity cycles have no significant baseline
defects, select five random worlds. Record the selection method and seed,
then run the same clean/continuity checks and log analysis for all five. A
failure returns the loop to diagnosis and repair; it does not waive the gate.

Final report
Return the fixed-baseline results, comparison, quality/efficiency/observability
findings, defects and fixes, commands run, artifacts and log paths, remaining
risks, and the five-world gate decision. State "gate blocked" unless every
hard blocker is cleared.
```
