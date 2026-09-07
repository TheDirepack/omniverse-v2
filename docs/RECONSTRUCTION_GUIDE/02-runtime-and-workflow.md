# 2. Runtime and workflow

## Durable run protocol

Creating a run requires an `Idempotency-Key`. The kernel hashes the strict
`CreateResearchRun` payload; reuse with identical payload returns the existing run,
while reuse with different data is a conflict. It creates a `run`, one `run_target`
per requested world, and one ordered `run_step` for every `StepKind` per target.
The worker leases eligible persisted steps, executes one step at a time, records an
attempt/checkpoint/effect, and periodically reclaims expired leases.

Run statuses are `PENDING`, `RUNNING`, `WAITING_RETRY`, `WAITING_INPUT`,
`CANCELLING`, `CANCELLED`, `SUCCEEDED`, and `FAILED`. Terminal states cannot
transition. Cancellation is noticed at a safe step boundary. Retryable failures must
have a due time and cannot exceed the configured step limit. A crash is left durable
for lease reconciliation rather than being silently reset.

```text
INVENTORY → PLAN → SCOUT → ACQUIRE → EXTRACT → SYNTHESIZE
                              → AUDIT → INTEGRATE → SUMMARIZE → COMPLETE
```

Successful work is idempotent through effect keys and model-step-effect records.
The workflow is intentionally restart-safe: a process crash after a committed model
call must replay the validated result without issuing a duplicate call or integration.

## What each step does

| Step | Responsibility | Durable outputs |
|---|---|---|
| INVENTORY | Creates workspace/brief scope and resolves existing research context. | workspace, coverage context |
| PLAN | Calls a structured planner under bounded question/query/source-slot limits. | plan/questions, context manifest, model call |
| SCOUT | Uses qualified wiki inventory first; otherwise configured bounded discovery/search. | wiki profile/pages or lead-only search records |
| ACQUIRE | Fetches approved URLs and creates/cache source revisions plus targeted passages. | source, revision, acquisition cache, blobs |
| EXTRACT | Calls an extractor constrained to source passages; validates exact excerpts. | evidence fragments |
| SYNTHESIZE | Produces field-scoped proposals and relationship candidates. | proposals, field evidence, conflicts |
| AUDIT | Audits each material assertion against policy and evidence. | audit decisions |
| INTEGRATE | Promotes accepted evidence-backed material into immutable canon revisions. | nodes/relationships/citations/effects |
| SUMMARIZE | Produces source-linked user-facing facts. | structured summary revision |
| COMPLETE | Computes complete/partial/failed/cancelled outcome and closes run. | final outcome, event |

## Research constraints

The strict contracts in `contracts.py` reject unknown model fields and impose bounded
planning. Scope always names world, subjects, continuity, timepoint, conditions, and
branch; UI users do not select arbitrary domains. Every synthesized material field
has separate supporting and contradicting evidence references. Relationship graphs
are validated, including cycle checks for acyclic inheritance/taxonomy edges.

Search snippets and generic leads are not evidence. Extraction succeeds only when
the exact claimed excerpt exists in an allowed authoritative source passage at the
recorded locator. MiniCPM output is tagged `UNTRUSTED_NON_EVIDENTIARY` and can never
replace a source excerpt. Integration rejects unknown, out-of-scope, lead-only,
incomplete, contradicted, or inadequately supported assertions. A proposal can remain
provisional and yield a gap/partial outcome rather than canon.

## Wiki, search, and acquisition

Wiki handling is deliberately capability-limited. Scout can make one `<world> wiki`
discovery per workspace when no qualified profile exists. It fetches a same-host
sitemap, caches inventory for the configured freshness period, and deterministically
queues title/alias/section-term matches. Models receive inventory/page identifiers,
not arbitrary browser access. Pending relevant wiki pages suppress open-web recovery;
external recovery requires an explicit policy.

`AcquisitionService` permits only validated HTTP(S) requests: every DNS answer and
redirect is checked against public-address policy, body size, timeout, status, and
content type rules. It tries direct HTTP then an eligible cloakbrowser fallback.
HTML/text is deterministically cleaned and targeted; PDFs use `pypdf`; images may use
Tesseract. Raw bytes, cleaned deterministic derivative, and model readability
derivative remain distinct cached blobs, keyed by canonical URL, policy, and target.

Search adapters include cached fallback and browser/API implementations for Google,
Bing, Brave, and DuckDuckGo. A Brave key is stored through the credential boundary.

## Models and routing

`ProviderRouter` reads providers, models, routes, candidates, credentials, and
health from SQLite. For a task it orders route candidates by position, filters by
capability and effective input window, then chooses eligible credentials with
weighted history. Authentication failures disable credentials; rate-limit/transient
failures create cooldowns and attempt the next candidate. `StructuredModelGateway`
validates Pydantic output and performs a single repair attempt for malformed JSON.

The development seed is an OpenAI-compatible `qwen-local` provider/model, a `DEFAULT`
route, and local-development credential; Qwen is the final normal fallback. MiniCPM
is a preprocessing helper, never a provider fallback. Optional SSH lifecycle control
starts/stops only configured MiniCPM/Qwen services and rejects shell metacharacters.
