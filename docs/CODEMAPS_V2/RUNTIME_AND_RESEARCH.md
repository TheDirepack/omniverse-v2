# Omniverse V2 Runtime and Research Workflow

V2 executes durable research. The worker leases persisted work and checkpoints outcomes so startup and periodic reconciliation can reclaim stale leases.

## Workflow

`ResearchWorker` polls eligible runs and calls `ResearchWorkflow.run_next()`.

```text
INVENTORY -> PLAN -> SCOUT -> ACQUIRE -> EXTRACT -> SYNTHESIZE
          -> AUDIT -> INTEGRATE -> SUMMARIZE -> COMPLETE
```

Successful steps create checkpoint and idempotency-effect records. Transient provider failures may retry. Provider, structured-output, and agent-output failures can produce partial outcomes. Cancellation occurs at a safe step boundary.

Search leads are not evidence. Acquisition creates source revisions and deterministic targeted passages. Extraction must quote an allowed authoritative passage exactly. Synthesis attaches evidence by material field, and audit gates promotion to canon. The workflow rejects out-of-scope, unknown, lead-only, and incomplete evidence.

Sources: `backend/app/v2/workflow.py`, `worker.py`, and `research_runs.py`.

## Acquisition and MiniCPM

`AcquisitionService` validates HTTP(S), DNS, redirects, public-address policy, body size, timeout, and content type. It tries HTTP first and uses cloakbrowser after eligible transport failures when browsing is enabled. Browser requests receive the same URL policy and use `backend/data/v2-secrets/browser-profile` by default.

PDF input uses `pypdf`; image input uses Tesseract through `pytesseract` when available. Results cache by canonical URL, policy, and targeting input.

MiniCPM reformats selected passages for readability after deterministic preprocessing. Its output has `UNTRUSTED_NON_EVIDENTIARY` metadata and cannot substitute for source excerpts. Configure it with `OMNIVERSE_V2_PREPROCESSOR_*`; optional SSH lifecycle management can start or stop MiniCPM and Qwen.

## Provider routing

Provider routes, candidates, models, credential references, and health are database-backed. `ProviderRouter` evaluates candidates in position order, filters for capabilities and context, then selects eligible credentials by weighted selection history. Auth errors disable credentials; rate-limit and transient errors apply cooldowns and allow fallback.

Initialization ensures `qwen-local`, a Qwen model, a `DEFAULT` route, and a local development credential when custom routes do not supersede them. Qwen is the V2 development final fallback. MiniCPM is not a provider fallback.

See [Persistence](PERSISTENCE.md) and [Operations](OPERATIONS.md).
