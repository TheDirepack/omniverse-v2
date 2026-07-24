# Role contracts stay compact and validation errors are stable workflow diagnostics.
# ruff: noqa: E501, TRY003

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.v2.acquisition import AcquisitionPolicy
from app.v2.bootstrap import BUILTIN_POLICIES
from app.v2.context import EvidenceItem
from app.v2.contracts import (
    AuditorOutput,
    AuditVerdict,
    ExtractorOutput,
    PlannerOutput,
    StructuredProposal,
    SummaryOutput,
    SynthesizerOutput,
)
from app.v2.domain import GraphEdge, RunOutcome, RunStatus, StepKind, ensure_valid_graph
from app.v2.gateway import StructuredModelGateway
from app.v2.models import (
    AuditDecisionRecord,
    CanonNode,
    CanonNodeRevision,
    ClaimConflict,
    CoverageRecord,
    EvidenceFragment,
    IntegrationEffect,
    MaterialProposalFieldRecord,
    MaterialProposalRecord,
    ModelCall,
    ModelStepEffect,
    NodeEvidence,
    PolicyDefinition,
    PromotionDecision,
    ProposalFieldEvidence,
    RelationshipAssertion,
    RelationshipEvidence,
    RelationshipRevision,
    ResearchGapRecord,
    ResearchWorkspace,
    SearchLead,
    Source,
    SourceRevision,
    StepEffect,
    WorkflowSummary,
    World,
)
from app.v2.providers import ErrorClass, ProviderError
from app.v2.research_runs import ResearchRunKernel
from app.v2.search import normalize_candidates

PROMPTS = {
    StepKind.PLAN: "planner/v1: Produce scoped questions, queries, indicators, budgets, and stop conditions. Output only the schema. Do not provide hidden reasoning.",
    StepKind.EXTRACT: "extractor/v1: Extract only exact source excerpts answering the supplied questions. Never use memory or snippets as evidence. Output only the schema.",
    StepKind.SYNTHESIZE: "synthesizer/v1: Produce typed proposals with field-level supporting and contradicting fragment IDs. Preserve qualifiers. Output only the schema.",
    StepKind.AUDIT: "auditor/v1: Independently judge every material field against exact excerpts and scope. Output stable verdicts and reason codes only.",
    StepKind.SUMMARIZE: "summary/v1: Summarize accepted canon only. Every fact must cite supplied node and fragment IDs. Output only the schema.",
}


def _stable(prefix: str, *parts: object) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def _scoped_model_id(kind: str, workspace_id: str, model_id: str) -> str:
    return _stable(kind, workspace_id, model_id)


def _resolve_fragment_id(session: Session, model_id: str, content_hash: str) -> str:
    existing = session.get(EvidenceFragment, model_id)
    if existing is None or existing.content_hash == content_hash:
        return model_id
    return _stable("fragment", content_hash)


class EvidenceEligibilityError(ValueError):
    pass


def policy_obligations(
    domains: tuple[str, ...], policy: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    policy = (
        policy
        or next(
            item
            for item in BUILTIN_POLICIES
            if item.policy_type == "RESEARCH_COMPLETION"
        ).definition_json
    )
    aliases = policy.get("aliases", {})
    definitions = policy["domains"]
    domains = domains or tuple(definitions)
    result = {}
    for requested in domains:
        policy_domain = aliases.get(requested, requested)
        if policy_domain not in definitions:
            raise ValueError(f"unknown research domain: {requested}")
        result[requested] = {
            "policy_domain": policy_domain,
            **definitions[policy_domain],
        }
    return result


def validate_promotion_source_policy(
    sources: tuple[dict[str, Any], ...],
    *,
    high_impact: bool,
    policy: dict[str, Any] | None = None,
) -> None:
    canon = (
        policy
        or next(
            item for item in BUILTIN_POLICIES if item.policy_type == "CANON"
        ).definition_json
    )
    source_policy = canon["promotion_sources"]
    eligible = set(source_policy["eligible_classes"])
    if any(
        str(source.get("source_class", "SECONDARY")).upper() not in eligible
        for source in sources
    ):
        raise EvidenceEligibilityError("ineligible source class for promotion")
    independent = {
        source.get("lineage_id") or source.get("source_id") for source in sources
    }
    if high_impact and len(independent) < int(
        source_policy["high_impact_min_independent"]
    ):
        raise EvidenceEligibilityError("high-impact field requires independent support")


@dataclass(frozen=True, slots=True)
class CompletionInputs:
    required_indicators: frozenset[str]
    accepted_indicators: frozenset[str]
    critical_questions: frozenset[str]
    accepted_questions: frozenset[str]
    allowed_gap_questions: frozenset[str]
    provenance_rate: float
    domain_coverage: dict[str, float]
    unresolved_invalidating_conflicts: int
    unresolved_audit_decisions: int
    duplicate_promotions: int


@dataclass(frozen=True, slots=True)
class CompletionResult:
    outcome: RunOutcome
    reasons: tuple[str, ...]


def evaluate_completion(inputs: CompletionInputs) -> CompletionResult:
    reasons: list[str] = []
    required = inputs.required_indicators
    accepted = inputs.accepted_indicators & required
    overall = len(accepted) / len(required) if required else 1.0
    unanswered = inputs.critical_questions - inputs.accepted_questions
    unallowed = unanswered - inputs.allowed_gap_questions
    if inputs.provenance_rate != 1.0:
        reasons.append("PROVENANCE_BELOW_1.0")
    if unallowed:
        reasons.append("CRITICAL_QUESTIONS_UNRESOLVED")
    if overall < 0.8:
        reasons.append("OVERALL_COVERAGE_BELOW_0.80")
    for domain, coverage in sorted(inputs.domain_coverage.items()):
        if coverage < 0.6:
            reasons.append(f"DOMAIN_COVERAGE_BELOW_0.60:{domain}")
    if inputs.unresolved_invalidating_conflicts:
        reasons.append("INVALIDATING_CONFLICTS_OPEN")
    if inputs.unresolved_audit_decisions:
        reasons.append("AUDIT_DECISIONS_UNRESOLVED")
    if inputs.duplicate_promotions:
        reasons.append("DUPLICATE_PROMOTIONS")
    return CompletionResult(
        RunOutcome.COMPLETE if not reasons else RunOutcome.PARTIAL, tuple(reasons)
    )


def validate_evidence_eligibility(
    target_scope,
    domain: str,
    supporting_ids: tuple[str, ...],
    contradicting_ids: tuple[str, ...],
    evidence: dict[str, dict[str, Any]],
    *,
    field_name: str = "field",
    field_value: Any = None,
) -> None:
    all_ids = {*supporting_ids, *contradicting_ids}
    unknown = all_ids - evidence.keys()
    if unknown:
        raise EvidenceEligibilityError("proposal references unknown evidence")
    qualifying_fields = {"qualifier", "limitation", "limits", "conditions"}
    for evidence_id in supporting_ids:
        item = evidence[evidence_id]
        role = item.get("support_role")
        if role == "QUALIFIES" and field_name not in qualifying_fields:
            raise EvidenceEligibilityError(
                "qualifier evidence must preserve its limitation"
            )
        if role == "QUALIFIES" and field_value in (None, "", (), []):
            raise EvidenceEligibilityError(
                "qualifier evidence requires a preserved value"
            )
        if role not in {"SUPPORTS", "QUALIFIES"}:
            raise EvidenceEligibilityError("evidence is not eligible support")
        checks = {
            "world": (item.get("world_id"), target_scope.world_id),
            "continuity": (item.get("continuity"), target_scope.continuity),
            "era": (item.get("era_or_timepoint"), target_scope.era_or_timepoint),
            "domain": (item.get("domain"), domain),
            "branch": (item.get("branch_id"), target_scope.branch_id),
            "conditions": (
                tuple(item.get("conditions", ())),
                tuple(target_scope.conditions),
            ),
        }
        for label, (actual, expected) in checks.items():
            if actual != expected:
                raise EvidenceEligibilityError(f"evidence {label} is out of scope")
        if not set(target_scope.subject_ids) & set(item.get("subject_ids", ())):
            raise EvidenceEligibilityError("evidence subject is out of scope")
    for evidence_id in contradicting_ids:
        if evidence[evidence_id].get("support_role") != "CONTRADICTS":
            raise EvidenceEligibilityError("contradicting link has the wrong role")


def validate_relationship_graph(
    edges: tuple[tuple[str, str, str], ...], audit_by_id: dict[str, Any]
) -> None:
    if len(audit_by_id) != len(set(audit_by_id)):
        raise ValueError("relationship audit decisions must be unique")
    ensure_valid_graph(tuple(GraphEdge(*edge) for edge in edges))


def independent_support_count(
    session: Session, source_revision_ids: tuple[str, ...]
) -> int:
    rows = session.execute(
        select(SourceRevision, Source)
        .join(Source)
        .where(SourceRevision.id.in_(source_revision_ids))
    ).all()
    return len(
        {
            (revision.content_hash, source.lineage_id or source.id)
            for revision, source in rows
        }
    )


class SimulatedCrashError(RuntimeError):
    pass


class ResearchWorkflow:
    def __init__(
        self,
        engine,
        kernel: ResearchRunKernel,
        router,
        search_provider,
        acquisition_service,
        *,
        max_gap_loops: int = 1,
        context_window: int = 40_000,
        acquisition_policy: AcquisitionPolicy | None = None,
        clock=None,
    ) -> None:
        self.engine = engine
        self.kernel = kernel
        self.gateway = StructuredModelGateway(engine, router)
        self.search = search_provider
        self.acquisition = acquisition_service
        self.max_gap_loops = max_gap_loops
        self.context_window = context_window
        self.acquisition_policy = acquisition_policy or AcquisitionPolicy()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.crash_after_effect_for: StepKind | None = None
        self.crash_after_model_call_for: StepKind | None = None

    def _policy(self, policy_type: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            stored = session.scalar(
                select(PolicyDefinition)
                .where(
                    PolicyDefinition.policy_type == policy_type,
                    PolicyDefinition.active.is_(True),
                )
                .order_by(PolicyDefinition.version.desc())
            )
        if stored is not None:
            return dict(stored.definition_json)
        return dict(
            next(
                item.definition_json
                for item in BUILTIN_POLICIES
                if item.policy_type == policy_type
            )
        )

    def _freshness_scope(self, lease) -> dict[str, str]:
        scope = self._scope(lease)
        return {
            "continuity": str(scope.get("continuity", "unspecified")),
            "era_or_timepoint": str(scope.get("era_or_timepoint", "unspecified")),
            "branch_id": str(scope.get("branch_id", "main")),
            "conditions_key": json.dumps(
                sorted(scope.get("conditions", ())), separators=(",", ":")
            ),
        }

    async def run(self, run_id: str, *, stop_after: StepKind | None = None):
        projection = self.kernel.get(run_id)
        if projection.outcome is not None:
            return projection
        completed_before = {
            step.id for step in projection.steps if step.status is RunStatus.SUCCEEDED
        }
        while await self.run_next(run_id):
            projection = self.kernel.get(run_id)
            newly_completed = [
                step
                for step in projection.steps
                if step.id not in completed_before
                and step.status is RunStatus.SUCCEEDED
            ]
            completed_before.update(step.id for step in newly_completed)
            if stop_after is not None and any(
                step.kind is stop_after for step in newly_completed
            ):
                return projection
        return self.kernel.get(run_id)

    async def run_next(self, run_id: str) -> bool:
        projection = self.kernel.get(run_id)
        if projection.outcome is not None:
            return False
        lease = self.kernel.lease_next(
            "research-workflow", self.clock(), timedelta(minutes=10), run_id=run_id
        )
        if lease is None:
            return False
        if self.kernel.get(run_id).status is RunStatus.CANCELLING:
            self.kernel.cancel_at_safe_boundary(lease, self.clock())
            return True
        try:
            state = await self._execute(lease)
            self._raise_simulated_crash(lease.kind)
            self.kernel.checkpoint_success(
                lease,
                effect_key=f"workflow:{lease.step_id}:v2",
                output_refs=tuple(str(value) for value in state.get("output_refs", ())),
                state=state,
                now=self.clock(),
            )
        except SimulatedCrashError:
            raise
        except Exception as error:  # Every leased failure must become inspectable.
            retryable = isinstance(error, ProviderError) and error.error_class in {
                ErrorClass.RATE_LIMIT,
                ErrorClass.TRANSIENT,
            }
            retry_seconds = (
                error.retry_after if isinstance(error, ProviderError) else None
            )
            self.kernel.checkpoint_failure(
                lease,
                f"{type(error).__name__}: {error}",
                retryable=retryable,
                retry_at=(
                    self.clock() + timedelta(seconds=retry_seconds or 30)
                    if retryable
                    else None
                ),
                now=self.clock(),
            )
        return True

    def _raise_simulated_crash(self, kind: StepKind) -> None:
        if self.crash_after_effect_for is kind:
            raise SimulatedCrashError("simulated crash after effect commit")

    async def _execute(self, lease) -> dict[str, Any]:
        handlers = {
            StepKind.INVENTORY: self._inventory,
            StepKind.PLAN: self._plan,
            StepKind.SCOUT: self._scout,
            StepKind.ACQUIRE: self._acquire,
            StepKind.EXTRACT: self._extract,
            StepKind.SYNTHESIZE: self._synthesize,
            StepKind.AUDIT: self._audit,
            StepKind.INTEGRATE: self._integrate,
            StepKind.SUMMARIZE: self._summarize,
            StepKind.COMPLETE: self._complete,
        }
        return await handlers[lease.kind](lease)

    def _target(self, lease):
        return next(
            target
            for target in self.kernel.get(lease.run_id).targets
            if target.id == lease.target_id
        )

    def _scope(self, lease) -> dict[str, Any]:
        projection = self.kernel.get(lease.run_id)
        return {**projection.scope, **self._target(lease).scope}

    @staticmethod
    def _workspace_id(target_id: str) -> str:
        return f"workspace:{target_id}"

    def _workspace(self, session: Session, lease) -> ResearchWorkspace:
        workspace_id = self._workspace_id(lease.target_id)
        workspace = session.get(ResearchWorkspace, workspace_id)
        if workspace is None:
            target = self._target(lease)
            workspace = ResearchWorkspace(
                id=workspace_id,
                run_id=lease.run_id,
                target_id=lease.target_id,
                world_id=lease.world_id,
                continuity=str(self._scope(lease).get("continuity", "unspecified")),
                era_or_timepoint=self._freshness_scope(lease)["era_or_timepoint"],
                branch_id=self._freshness_scope(lease)["branch_id"],
                conditions_key=self._freshness_scope(lease)["conditions_key"],
                brief_json={"objective": target.objective, "scope": self._scope(lease)},
                status="ACTIVE",
            )
            session.add(workspace)
            session.flush()
        return workspace

    def _state(self, lease) -> dict[str, Any]:
        with Session(self.engine) as session:
            workspace = session.get(
                ResearchWorkspace, self._workspace_id(lease.target_id)
            )
            return dict(workspace.brief_json) if workspace else {}

    def _save(self, lease, **values: Any) -> dict[str, Any]:
        with Session(self.engine) as session, session.begin():
            workspace = self._workspace(session, lease)
            state = dict(workspace.brief_json)
            state.update(values)
            workspace.brief_json = state
            return state

    async def _model_call(self, lease, *, effect_suffix: str = "main", **kwargs):
        effect_key = f"model:{lease.step_id}:{effect_suffix}"
        output_type = kwargs["output_type"]
        with Session(self.engine) as session:
            existing = session.get(ModelStepEffect, effect_key)
            if existing is not None:
                return output_type.model_validate(existing.output_json, strict=True)
            model_call = session.get(ModelCall, effect_key)
            if model_call is not None:
                output = output_type.model_validate_json(
                    json.dumps(model_call.response_json), strict=True
                )
            else:
                output = None
        if output is None:
            output = await self.gateway.call(
                run_id=lease.run_id,
                model_call_id=effect_key,
                step_id=lease.step_id,
                **kwargs,
            )
            if self.crash_after_model_call_for is lease.kind:
                raise SimulatedCrashError("simulated crash after model call commit")
        with Session(self.engine) as session, session.begin():
            if session.get(ModelStepEffect, effect_key) is None:
                model_call = session.get(ModelCall, effect_key)
                session.add(
                    ModelStepEffect(
                        effect_key=effect_key,
                        step_id=lease.step_id,
                        task=kwargs["task"],
                        prompt_version=kwargs["role_prompt"].split(":", 1)[0],
                        schema_version=output_type.__name__,
                        output_json=output.model_dump(mode="json"),
                        manifest_id=model_call.manifest_id if model_call else None,
                        model_call_id=effect_key,
                    )
                )
        return output

    async def _inventory(self, lease) -> dict[str, Any]:
        target = self._target(lease)
        scope = self._scope(lease)
        domains = tuple(scope.get("domains") or policy_obligations(()))
        continuity = str(scope.get("continuity", "unspecified"))
        freshness = self._freshness_scope(lease)
        workspace_id = self._workspace_id(lease.target_id)
        with Session(self.engine) as session:
            world = session.get(World, target.world_id)
            if world is None:
                raise LookupError(target.world_id)
            prior_coverage = session.scalars(
                select(CoverageRecord).where(
                    CoverageRecord.world_id == target.world_id,
                    CoverageRecord.continuity == continuity,
                    CoverageRecord.era_or_timepoint == freshness["era_or_timepoint"],
                    CoverageRecord.branch_id == freshness["branch_id"],
                    CoverageRecord.conditions_key == freshness["conditions_key"],
                    CoverageRecord.status == "VERIFIED",
                )
            ).all()
            obligations = policy_obligations(
                domains, self._policy("RESEARCH_COMPLETION")
            )
            covered = {
                domain
                for domain in domains
                if len(
                    {
                        indicator
                        for row in prior_coverage
                        if row.domain == domain
                        for indicator in row.indicators_json
                    }
                )
                / len(obligations[domain]["required_indicators"])
                >= 0.6
            }
            gaps = session.scalars(
                select(ResearchGapRecord)
                .join(ResearchWorkspace)
                .where(
                    ResearchWorkspace.world_id == target.world_id,
                    ResearchWorkspace.continuity == continuity,
                    ResearchWorkspace.era_or_timepoint == freshness["era_or_timepoint"],
                    ResearchWorkspace.branch_id == freshness["branch_id"],
                    ResearchWorkspace.conditions_key == freshness["conditions_key"],
                )
            ).all()
            conflicts = session.scalars(
                select(ClaimConflict)
                .join(ResearchWorkspace)
                .where(
                    ResearchWorkspace.world_id == target.world_id,
                    ResearchWorkspace.continuity == continuity,
                    ResearchWorkspace.era_or_timepoint == freshness["era_or_timepoint"],
                    ResearchWorkspace.branch_id == freshness["branch_id"],
                    ResearchWorkspace.conditions_key == freshness["conditions_key"],
                )
            ).all()
            revisions = session.scalars(
                select(EvidenceFragment.source_revision_id).where(
                    EvidenceFragment.world_id == target.world_id,
                    EvidenceFragment.continuity == continuity,
                    EvidenceFragment.era_or_timepoint == freshness["era_or_timepoint"],
                    EvidenceFragment.branch_id == freshness["branch_id"],
                    EvidenceFragment.conditions_json
                    == sorted(scope.get("conditions", ())),
                )
            ).all()
            accepted_revisions = session.execute(
                select(CanonNode.id, CanonNodeRevision.scope_json)
                .join(CanonNodeRevision)
                .where(CanonNode.world_id == target.world_id)
            ).all()
            accepted_nodes = [
                node_id
                for node_id, revision_scope in accepted_revisions
                if str(revision_scope.get("continuity", "unspecified"))
                == freshness["continuity"]
                and str(revision_scope.get("era_or_timepoint", "unspecified"))
                == freshness["era_or_timepoint"]
                and str(revision_scope.get("branch_id", "main"))
                == freshness["branch_id"]
                and json.dumps(
                    sorted(revision_scope.get("conditions", ())),
                    separators=(",", ":"),
                )
                == freshness["conditions_key"]
            ]
        inventory = {
            "world": {
                "id": world.id,
                "name": world.name,
                "continuity": world.continuity,
            },
            "missing_domains": [domain for domain in domains if domain not in covered],
            "gap_ids": [gap.id for gap in gaps],
            "conflict_ids": [
                conflict.id for conflict in conflicts if conflict.status != "RESOLVED"
            ],
            "source_revision_ids": list(revisions),
            "accepted_node_ids": list(accepted_nodes),
        }
        return self._save(lease, inventory=inventory, output_refs=[workspace_id])

    async def _plan(self, lease) -> dict[str, Any]:
        state = self._state(lease)
        missing = state["inventory"]["missing_domains"]
        if not missing:
            return self._save(lease, plan={"questions": []})
        obligations = policy_obligations(
            tuple(missing), self._policy("RESEARCH_COMPLETION")
        )
        output = await self._model_call(
            lease,
            task="research.plan",
            role_prompt=PROMPTS[StepKind.PLAN],
            payload={
                "inventory": state["inventory"],
                "objective": self._target(lease).objective,
                "policy_obligations": obligations,
            },
            output_type=PlannerOutput,
            context_window=self.context_window,
        )
        ids: set[str] = set()
        text: set[str] = set()
        queries: set[str] = set()
        for item in output.questions:
            key = item.question.casefold().strip()
            if item.id in ids or key in text:
                raise ValueError("duplicate plan item")
            if item.domain not in missing:
                raise ValueError("out-of-scope plan item")
            normalized_queries = {query.casefold().strip() for query in item.queries}
            if (
                len(normalized_queries) != len(item.queries)
                or normalized_queries & queries
            ):
                raise ValueError("duplicate plan query")
            ids.add(item.id)
            text.add(key)
            queries.update(normalized_queries)
        for domain, obligation in obligations.items():
            planned = {
                indicator
                for item in output.questions
                if item.domain == domain
                for indicator in item.required_indicators
            }
            if not set(obligation["required_indicators"]) <= planned:
                raise ValueError(f"planner omitted policy obligations for {domain}")
        return self._save(lease, plan=output.model_dump(mode="json"))

    async def _scout(self, lease) -> dict[str, Any]:
        questions = self._state(lease).get("plan", {}).get("questions", [])
        workspace_id = self._workspace_id(lease.target_id)
        found = []
        for question in questions:
            for query in question["queries"]:
                values = await self.search.search(
                    query, limit=question["source_budget"]
                )
                found.extend(
                    (question, query, candidate)
                    for candidate in normalize_candidates(
                        values, question["source_budget"]
                    )
                )
        with Session(self.engine) as session, session.begin():
            self._workspace(session, lease)
            for question, query, candidate in found:
                lead_id = _stable("lead", workspace_id, candidate.canonical_url)
                if session.get(SearchLead, lead_id) is None:
                    session.add(
                        SearchLead(
                            id=lead_id,
                            workspace_id=workspace_id,
                            question_id=question["id"],
                            query=query,
                            canonical_url=candidate.canonical_url,
                            title=candidate.title,
                            snippet=candidate.snippet,
                            rank=candidate.rank,
                            source_class=candidate.source_class,
                            publisher=candidate.publisher,
                            lineage_id=candidate.lineage_id,
                        )
                    )
            leads = session.scalars(
                select(SearchLead)
                .where(SearchLead.workspace_id == workspace_id)
                .order_by(SearchLead.rank, SearchLead.canonical_url)
            ).all()
            payload = [
                {
                    "id": lead.id,
                    "url": lead.canonical_url,
                    "question_id": lead.question_id,
                    "source_class": lead.source_class,
                    "publisher": lead.publisher,
                    "lineage_id": lead.lineage_id,
                }
                for lead in leads
            ]
        return self._save(lease, leads=payload)

    async def _acquire(self, lease) -> dict[str, Any]:
        acquired = []
        for lead in self._state(lease).get("leads", []):
            result = await self.acquisition.acquire(
                lead["url"],
                self.acquisition_policy,
                idempotency_key=f"{lease.target_id}:{lead['id']}",
                attempt_id=str(lease.attempt_number),
                step_id=lease.step_id,
                source_class=lead["source_class"],
                publisher=lead.get("publisher"),
                lineage_id=lead.get("lineage_id"),
            )
            acquired.append(
                {
                    "lead_id": lead["id"],
                    "question_id": lead["question_id"],
                    "source_id": result.source_id,
                    "revision_id": result.revision_id,
                    "blob_hash": result.blob_hash,
                    "content_type": result.content_type,
                    "extract": result.extract,
                }
            )
        return self._save(lease, acquired=acquired)

    async def _extract(self, lease) -> dict[str, Any]:
        state = self._state(lease)
        questions = {
            item["id"]: item for item in state.get("plan", {}).get("questions", [])
        }
        fragment_ids: list[str] = []
        for source in state.get("acquired", []):
            full_body = (
                source.get("extract", "")
                if source.get("content_type") == "application/pdf"
                else self.acquisition.blobs.get(source["blob_hash"]).decode(
                    "utf-8", errors="replace"
                )
            )
            # One extraction call receives one deterministic bounded chunk.
            body = full_body[
                : self.gateway.allocator.extraction_character_budget(
                    self.context_window, "OPENAI"
                )
            ]
            output = await self._model_call(
                lease,
                effect_suffix=source["revision_id"],
                task="research.extract",
                role_prompt=PROMPTS[StepKind.EXTRACT],
                payload={
                    "source_revision_id": source["revision_id"],
                    "source_body": body,
                    "questions": [questions[source["question_id"]]],
                },
                output_type=ExtractorOutput,
                context_window=self.context_window,
            )
            with Session(self.engine) as session, session.begin():
                for fragment in output.fragments:
                    if fragment.source_revision_id != source["revision_id"]:
                        raise ValueError(
                            "fragment references the wrong source revision"
                        )
                    if fragment.exact_excerpt not in full_body:
                        raise ValueError(
                            "exact excerpt does not occur in acquired source body"
                        )
                    expected_continuity = str(
                        self._scope(lease).get("continuity", "unspecified")
                    )
                    if fragment.continuity != expected_continuity:
                        raise ValueError("evidence continuity is out of scope")
                    if fragment.support_role == "LEAD_ONLY":
                        raise ValueError(
                            "search snippets and leads cannot become evidence"
                        )
                    content_hash = hashlib.sha256(
                        f"{fragment.source_revision_id}\0{fragment.locator}\0{fragment.exact_excerpt}".encode()
                    ).hexdigest()
                    existing = session.scalar(
                        select(EvidenceFragment).where(
                            EvidenceFragment.content_hash == content_hash
                        )
                    )
                    if existing is None:
                        record_id = _resolve_fragment_id(
                            session, fragment.fragment_id, content_hash
                        )
                        existing = EvidenceFragment(
                            id=record_id,
                            source_revision_id=fragment.source_revision_id,
                            locator=fragment.locator,
                            exact_excerpt=fragment.exact_excerpt,
                            content_hash=content_hash,
                            normalized_statement=fragment.normalized_statement,
                            domain=fragment.domain,
                            subject_ids_json=list(fragment.subject_ids),
                            continuity=fragment.continuity,
                            temporal_scope_json=fragment.temporal_scope.model_dump(
                                mode="json"
                            ),
                            support_role=fragment.support_role,
                            extraction_confidence=int(
                                fragment.extraction_confidence * 100
                            ),
                            world_id=lease.world_id,
                            era_or_timepoint=str(
                                self._scope(lease).get(
                                    "era_or_timepoint", "unspecified"
                                )
                            ),
                            branch_id=fragment.temporal_scope.branch_id,
                            conditions_json=sorted(fragment.conditions),
                        )
                        session.add(existing)
                    fragment_ids.append(existing.id)
        return self._save(lease, fragment_ids=sorted(set(fragment_ids)))

    def _evidence_items(self, fragment_ids: list[str]) -> tuple[EvidenceItem, ...]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(EvidenceFragment).where(EvidenceFragment.id.in_(fragment_ids))
            ).all()
            return tuple(
                EvidenceItem(
                    row.id,
                    row.source_revision_id,
                    "unintegrated",
                    row.exact_excerpt,
                    index,
                    contradiction=row.support_role == "CONTRADICTS",
                )
                for index, row in enumerate(rows)
            )

    async def _synthesize(self, lease) -> dict[str, Any]:
        state = self._state(lease)
        ids = state.get("fragment_ids", [])
        if not ids:
            return self._save(lease, synthesis={"proposals": [], "relationships": []})
        output = await self._model_call(
            lease,
            task="research.synthesize",
            role_prompt=PROMPTS[StepKind.SYNTHESIZE],
            payload={"scope": self._scope(lease), "fragment_ids": ids},
            output_type=SynthesizerOutput,
            evidence=self._evidence_items(ids),
            context_window=self.context_window,
        )
        known = set(ids)
        with Session(self.engine) as session:
            evidence_rows = session.scalars(
                select(EvidenceFragment).where(EvidenceFragment.id.in_(ids))
            ).all()
        evidence = {
            row.id: {
                "support_role": row.support_role,
                "world_id": row.world_id,
                "subject_ids": list(row.subject_ids_json),
                "continuity": row.continuity,
                "era_or_timepoint": row.era_or_timepoint,
                "branch_id": row.branch_id,
                "conditions": list(row.conditions_json),
                "domain": row.domain,
            }
            for row in evidence_rows
        }
        target = self._target(lease)
        for proposal in output.proposals:
            if set(proposal.fields) != set(proposal.field_evidence):
                raise ValueError("every material field requires field-level evidence")
            for links in proposal.field_evidence.values():
                if not {*links.supporting, *links.contradicting} <= known:
                    raise ValueError("proposal references unknown evidence")
            if proposal.scope.world_id != target.world_id:
                raise ValueError("proposal is out of world scope")
            expected_scope = self._scope(lease)
            if proposal.scope.continuity != expected_scope.get("continuity"):
                raise ValueError("proposal is out of continuity scope")
            if proposal.scope.era_or_timepoint != expected_scope.get(
                "era_or_timepoint", "unspecified"
            ):
                raise ValueError("proposal is out of era scope")
            if proposal.scope.branch_id != expected_scope.get("branch_id", "main"):
                raise ValueError("proposal is out of branch scope")
            if tuple(proposal.scope.conditions) != tuple(
                expected_scope.get("conditions", ())
            ):
                raise ValueError("proposal is out of conditions scope")
            for field_name, links in proposal.field_evidence.items():
                validate_evidence_eligibility(
                    proposal.scope,
                    str(
                        next(
                            iter(
                                {evidence[item]["domain"] for item in links.supporting}
                            )
                        )
                    ),
                    links.supporting,
                    links.contradicting,
                    evidence,
                    field_name=field_name,
                    field_value=proposal.fields[field_name],
                )
            quantity = proposal.fields.get("quantity")
            if quantity is not None and not proposal.fields.get("unit"):
                raise ValueError("quantities require units")
        for relationship in output.relationships:
            if relationship.scope.world_id != target.world_id:
                raise ValueError("relationship is out of world scope")
            if not set(relationship.evidence_fragment_ids) <= known:
                raise ValueError("relationship references unknown evidence")
        return self._save(lease, synthesis=output.model_dump(mode="json"))

    async def _audit(self, lease) -> dict[str, Any]:
        state = self._state(lease)
        raw = state.get("synthesis", {"proposals": [], "relationships": []})
        if not raw["proposals"]:
            return self._save(lease, audit={"decisions": []})
        with Session(self.engine) as session:
            evidence_rows = session.execute(
                select(EvidenceFragment, SourceRevision, Source)
                .join(
                    SourceRevision,
                    SourceRevision.id == EvidenceFragment.source_revision_id,
                )
                .join(Source, Source.id == SourceRevision.source_id)
                .where(EvidenceFragment.id.in_(state["fragment_ids"]))
            ).all()
        audit_context = {
            "synthesis": raw,
            "canon_policy": next(
                {
                    "id": item.id,
                    "version": item.version,
                    "definition": item.definition_json,
                }
                for item in BUILTIN_POLICIES
                if item.policy_type == "CANON"
            ),
            "evidence": [
                {
                    "fragment_id": fragment.id,
                    "support_role": fragment.support_role,
                    "source_revision_id": revision.id,
                    "source_class": source.source_class,
                    "publisher": source.publisher,
                    "lineage_id": source.lineage_id or source.id,
                    "scope": fragment.temporal_scope_json,
                }
                for fragment, revision, source in evidence_rows
            ],
            "qualifiers": [
                fragment.id
                for fragment, _revision, _source in evidence_rows
                if fragment.support_role == "QUALIFIES"
            ],
            "contradiction_set": [
                fragment.id
                for fragment, _revision, _source in evidence_rows
                if fragment.support_role == "CONTRADICTS"
            ],
        }
        output = await self._model_call(
            lease,
            task="research.audit",
            role_prompt=PROMPTS[StepKind.AUDIT],
            payload=audit_context,
            output_type=AuditorOutput,
            evidence=self._evidence_items(state["fragment_ids"]),
            context_window=self.context_window,
        )
        expected = {
            ("FIELD", f"{p['proposal_id']}:{field}")
            for p in raw["proposals"]
            for field in p["fields"]
        } | {
            ("RELATIONSHIP", relationship["relationship_id"])
            for relationship in raw["relationships"]
        }
        actual = {(d.assertion_type, d.assertion_id) for d in output.decisions}
        if expected != actual or len(actual) != len(output.decisions):
            raise ValueError("audit must decide every assertion exactly once")
        known = set(state["fragment_ids"])
        if any(
            not set(decision.evidence_fragment_ids) <= known
            for decision in output.decisions
        ):
            raise ValueError("audit references unknown evidence")
        with Session(self.engine) as session:
            model_call = session.get(ModelCall, f"model:{lease.step_id}:main")
        decisions = [
            decision.model_copy(
                update={
                    "policy_version": "audit.v1",
                    "model_call_id": model_call.id if model_call else None,
                    "manifest_id": model_call.manifest_id if model_call else None,
                }
            ).model_dump(mode="json")
            for decision in output.decisions
        ]
        return self._save(lease, audit={"decisions": decisions})

    async def _integrate(self, lease) -> dict[str, Any]:
        with Session(self.engine) as session:
            prior_step = session.get(StepEffect, lease.step_id)
            if prior_step is not None:
                return self._save(lease, **dict(prior_step.effect_json))
        state = self._state(lease)
        decisions = {
            (item["assertion_type"], item["assertion_id"]): item
            for item in state.get("audit", {}).get("decisions", [])
        }
        accepted: list[str] = []
        accepted_record_ids: list[str] = []
        mapping: dict[str, dict[str, str]] = {}
        canon_policy = self._policy("CANON")
        high_impact_fields = set(canon_policy["high_impact_fields"])
        completion_policy = self._policy("RESEARCH_COMPLETION")
        freshness = self._freshness_scope(lease)
        with Session(self.engine) as session, session.begin():
            workspace = self._workspace(session, lease)
            for raw in state.get("synthesis", {}).get("proposals", []):
                proposal = StructuredProposal.model_validate_json(
                    json.dumps(raw, sort_keys=True), strict=True
                )
                proposal_record_id = _scoped_model_id(
                    "proposal", workspace.id, proposal.proposal_id
                )
                material = [
                    decisions.get(("FIELD", f"{proposal.proposal_id}:{name}"))
                    for name in proposal.fields
                ]
                fully_accepted = (
                    bool(material)
                    and all(
                        item and item["verdict"] == AuditVerdict.ACCEPT.value
                        for item in material
                    )
                    and all(
                        not proposal.field_evidence[name].contradicting
                        for name in proposal.fields
                    )
                )
                if fully_accepted:
                    try:
                        for name, links in proposal.field_evidence.items():
                            source_rows = (
                                session.execute(
                                    select(Source)
                                    .join(SourceRevision)
                                    .join(EvidenceFragment)
                                    .where(EvidenceFragment.id.in_(links.supporting))
                                )
                                .scalars()
                                .all()
                            )
                            validate_promotion_source_policy(
                                tuple(
                                    {
                                        "source_id": source.id,
                                        "source_class": source.source_class,
                                        "lineage_id": source.lineage_id,
                                    }
                                    for source in source_rows
                                ),
                                high_impact=name in high_impact_fields
                                or bool(links.contradicting),
                                policy=canon_policy,
                            )
                    except EvidenceEligibilityError:
                        fully_accepted = False
                proposal_record = session.get(
                    MaterialProposalRecord, proposal_record_id
                )
                if proposal_record is None:
                    proposal_record = MaterialProposalRecord(
                        id=proposal_record_id,
                        workspace_id=workspace.id,
                        kind=proposal.kind.value,
                        scope_json=proposal.scope.model_dump(mode="json"),
                        fields_json=proposal.fields,
                    )
                    session.add(proposal_record)
                    session.flush()
                for name, value in proposal.fields.items():
                    field_id = _stable("field", proposal_record_id, name)
                    field = session.get(MaterialProposalFieldRecord, field_id)
                    if field is None:
                        field = MaterialProposalFieldRecord(
                            id=field_id,
                            proposal_id=proposal_record_id,
                            name=name,
                            value_json=value,
                        )
                        session.add(field)
                        session.flush()
                    links = proposal.field_evidence[name]
                    for fragment_id in links.supporting:
                        if (
                            session.get(
                                ProposalFieldEvidence,
                                (field_id, fragment_id, "SUPPORTS"),
                            )
                            is None
                        ):
                            session.add(
                                ProposalFieldEvidence(
                                    proposal_field_id=field_id,
                                    evidence_fragment_id=fragment_id,
                                    support_role="SUPPORTS",
                                )
                            )
                    for fragment_id in links.contradicting:
                        if (
                            session.get(
                                ProposalFieldEvidence,
                                (field_id, fragment_id, "CONTRADICTS"),
                            )
                            is None
                        ):
                            session.add(
                                ProposalFieldEvidence(
                                    proposal_field_id=field_id,
                                    evidence_fragment_id=fragment_id,
                                    support_role="CONTRADICTS",
                                )
                            )
                        conflict_id = _stable("conflict", field_id, fragment_id)
                        if session.get(ClaimConflict, conflict_id) is None:
                            session.add(
                                ClaimConflict(
                                    id=conflict_id,
                                    proposal_field_id=field_id,
                                    workspace_id=workspace.id,
                                    status="OPEN",
                                    resolution_json=None,
                                )
                            )
                    decision = decisions.get(
                        ("FIELD", f"{proposal.proposal_id}:{name}")
                    )
                    audit_id = _stable("audit", proposal_record_id, name)
                    if decision and session.get(AuditDecisionRecord, audit_id) is None:
                        session.add(
                            AuditDecisionRecord(
                                id=audit_id,
                                proposal_id=proposal_record_id,
                                field_name=name,
                                verdict=decision["verdict"],
                                reason_code=decision["reason_code"],
                                assertion_type=decision["assertion_type"],
                                assertion_id=decision["assertion_id"],
                                evidence_fragment_ids_json=decision[
                                    "evidence_fragment_ids"
                                ],
                                policy_version=decision["policy_version"],
                                model_call_id=decision.get("model_call_id"),
                                manifest_id=decision.get("manifest_id"),
                            )
                        )
                promotion_id = _stable("promotion", proposal_record_id)
                if session.get(PromotionDecision, promotion_id) is None:
                    audit_manifest_id = next(
                        (
                            item.get("manifest_id")
                            for item in material
                            if item and item.get("manifest_id")
                        ),
                        None,
                    )
                    session.add(
                        PromotionDecision(
                            id=promotion_id,
                            proposal_id=proposal_record_id,
                            decision="ACCEPT" if fully_accepted else "REJECT",
                            policy_version="promotion.v1",
                            audit_manifest_id=audit_manifest_id,
                        )
                    )
                if not fully_accepted:
                    continue
                effect_key = _stable(
                    "integration", proposal_record_id, sorted(state["fragment_ids"])
                )
                prior = session.get(IntegrationEffect, effect_key)
                if prior is None:
                    name = (
                        str(proposal.fields.get("name", proposal.proposal_id))
                        .casefold()
                        .strip()
                    )
                    node_id = _stable(
                        "node",
                        proposal.scope.world_id,
                        proposal.kind.value,
                        name,
                        proposal.scope.model_dump(mode="json"),
                    )
                    node = session.get(CanonNode, node_id)
                    if node is None:
                        node = CanonNode(
                            id=node_id,
                            world_id=proposal.scope.world_id,
                            kind=proposal.kind.value,
                            modality=proposal.fields.get("modality"),
                        )
                        session.add(node)
                        session.flush()
                    equivalent = session.scalar(
                        select(CanonNodeRevision).where(
                            CanonNodeRevision.node_id == node_id,
                            CanonNodeRevision.fields_json == proposal.fields,
                            CanonNodeRevision.scope_json
                            == proposal.scope.model_dump(mode="json"),
                        )
                    )
                    if equivalent is not None:
                        revision_id = equivalent.id
                        for field_name, links in proposal.field_evidence.items():
                            for fragment_id in links.supporting:
                                if (
                                    session.get(
                                        NodeEvidence,
                                        (revision_id, fragment_id, field_name),
                                    )
                                    is None
                                ):
                                    session.add(
                                        NodeEvidence(
                                            node_revision_id=revision_id,
                                            evidence_fragment_id=fragment_id,
                                            field_name=field_name,
                                        )
                                    )
                        session.add(
                            IntegrationEffect(
                                effect_key=effect_key,
                                proposal_id=proposal_record_id,
                                node_revision_id=revision_id,
                            )
                        )
                        accepted.append(proposal.proposal_id)
                        accepted_record_ids.append(proposal_record_id)
                        mapping[proposal.proposal_id] = {
                            "node_id": node_id,
                            "node_revision_id": revision_id,
                        }
                        continue
                    revision_number = (
                        session.scalar(
                            select(func.max(CanonNodeRevision.revision_number)).where(
                                CanonNodeRevision.node_id == node_id
                            )
                        )
                        or 0
                    ) + 1
                    revision_id = _stable(
                        "node-revision", node_id, revision_number, proposal.fields
                    )
                    session.add(
                        CanonNodeRevision(
                            id=revision_id,
                            node_id=node_id,
                            revision_number=revision_number,
                            fields_json=proposal.fields,
                            scope_json=proposal.scope.model_dump(mode="json"),
                        )
                    )
                    session.flush()
                    for field_name, links in proposal.field_evidence.items():
                        for fragment_id in links.supporting:
                            session.add(
                                NodeEvidence(
                                    node_revision_id=revision_id,
                                    evidence_fragment_id=fragment_id,
                                    field_name=field_name,
                                )
                            )
                    session.add(
                        IntegrationEffect(
                            effect_key=effect_key,
                            proposal_id=proposal_record_id,
                            node_revision_id=revision_id,
                        )
                    )
                accepted.append(proposal.proposal_id)
                accepted_record_ids.append(proposal_record_id)
                effect = session.scalar(
                    select(IntegrationEffect).where(
                        IntegrationEffect.proposal_id == proposal_record_id
                    )
                )
                if effect is not None:
                    revision = session.get(CanonNodeRevision, effect.node_revision_id)
                    assert revision is not None
                    mapping[proposal.proposal_id] = {
                        "node_id": revision.node_id,
                        "node_revision_id": revision.id,
                    }
            accepted_set = set(accepted)
            relationship_edges: list[tuple[str, str, str]] = []
            for relationship in state.get("synthesis", {}).get("relationships", []):
                source_id = relationship["source_proposal_id"]
                target_id = relationship["target_proposal_id"]
                source_record_id = _scoped_model_id("proposal", workspace.id, source_id)
                target_record_id = _scoped_model_id("proposal", workspace.id, target_id)
                if source_id not in accepted_set or target_id not in accepted_set:
                    continue
                audit = decisions.get(("RELATIONSHIP", relationship["relationship_id"]))
                if audit is not None:
                    relationship_audit_id = _stable(
                        "audit",
                        "relationship",
                        workspace.id,
                        relationship["relationship_id"],
                    )
                    if session.get(AuditDecisionRecord, relationship_audit_id) is None:
                        session.add(
                            AuditDecisionRecord(
                                id=relationship_audit_id,
                                proposal_id=source_record_id,
                                field_name="relationship",
                                verdict=audit["verdict"],
                                reason_code=audit["reason_code"],
                                assertion_type="RELATIONSHIP",
                                assertion_id=relationship["relationship_id"],
                                evidence_fragment_ids_json=audit[
                                    "evidence_fragment_ids"
                                ],
                                policy_version=audit["policy_version"],
                                model_call_id=audit.get("model_call_id"),
                                manifest_id=audit.get("manifest_id"),
                            )
                        )
                if audit is None or audit["verdict"] != AuditVerdict.ACCEPT.value:
                    continue
                if not relationship["evidence_fragment_ids"]:
                    continue
                source_effect = session.scalar(
                    select(IntegrationEffect)
                    .where(IntegrationEffect.proposal_id == source_record_id)
                    .order_by(IntegrationEffect.effect_key)
                )
                target_effect = session.scalar(
                    select(IntegrationEffect)
                    .where(IntegrationEffect.proposal_id == target_record_id)
                    .order_by(IntegrationEffect.effect_key)
                )
                if source_effect is None or target_effect is None:
                    continue
                source_revision = session.get(
                    CanonNodeRevision, source_effect.node_revision_id
                )
                target_revision = session.get(
                    CanonNodeRevision, target_effect.node_revision_id
                )
                assertion_id = _stable(
                    "relationship",
                    source_revision.node_id,
                    target_revision.node_id,
                    relationship["relation_type"],
                )
                relationship_edges.append(
                    (
                        source_revision.node_id,
                        target_revision.node_id,
                        relationship["relation_type"],
                    )
                )
                existing_edges = session.execute(
                    select(
                        RelationshipAssertion.source_node_id,
                        RelationshipAssertion.target_node_id,
                        RelationshipRevision.relation_type,
                    ).join(RelationshipRevision)
                ).all()
                ensure_valid_graph(
                    tuple(
                        GraphEdge(source, target, relation_type)
                        for source, target, relation_type in [
                            *existing_edges,
                            *relationship_edges,
                        ]
                    )
                )
                assertion = session.get(RelationshipAssertion, assertion_id)
                if assertion is None:
                    session.add(
                        RelationshipAssertion(
                            id=assertion_id,
                            source_node_id=source_revision.node_id,
                            target_node_id=target_revision.node_id,
                        )
                    )
                    session.flush()
                revision_id = _stable(
                    "relationship-revision",
                    assertion_id,
                    relationship["scope"],
                    relationship.get("valid_from"),
                    relationship.get("valid_to"),
                )
                if session.get(RelationshipRevision, revision_id) is None:
                    session.add(
                        RelationshipRevision(
                            id=revision_id,
                            assertion_id=assertion_id,
                            revision_number=1,
                            relation_type=relationship["relation_type"],
                            scope_json=relationship["scope"],
                            valid_from=relationship.get("valid_from"),
                            valid_to=relationship.get("valid_to"),
                        )
                    )
                    session.flush()
                    for fragment_id in relationship["evidence_fragment_ids"]:
                        if fragment_id not in state["fragment_ids"]:
                            raise ValueError("relationship references unknown evidence")
                        session.add(
                            RelationshipEvidence(
                                relationship_revision_id=revision_id,
                                evidence_fragment_id=fragment_id,
                                field_name="relationship",
                            )
                        )
            inventory = state.get("inventory", {})
            for domain in inventory.get("missing_domains", []):
                coverage_id = _stable(
                    "coverage",
                    workspace.id,
                    inventory["world"]["id"],
                    domain,
                    freshness,
                )
                coverage = session.get(CoverageRecord, coverage_id)
                if coverage is None:
                    session.add(
                        CoverageRecord(
                            id=coverage_id,
                            workspace_id=workspace.id,
                            world_id=inventory["world"]["id"],
                            domain=domain,
                            continuity=str(
                                self._scope(lease).get("continuity", "unspecified")
                            ),
                            era_or_timepoint=freshness["era_or_timepoint"],
                            branch_id=freshness["branch_id"],
                            conditions_key=freshness["conditions_key"],
                            status="VERIFIED" if accepted else "GAP",
                            indicators_json=sorted(
                                {
                                    indicator
                                    for indicator in policy_obligations(
                                        (domain,), completion_policy
                                    )[domain]["required_indicators"]
                                    if any(
                                        indicator in proposal.get("fields", {})
                                        for proposal in state.get("synthesis", {}).get(
                                            "proposals", []
                                        )
                                        if proposal["proposal_id"] in accepted
                                    )
                                }
                            ),
                        )
                    )
            effect_state = {
                "accepted_proposal_ids": accepted,
                "accepted_record_ids": accepted_record_ids,
                "proposal_canon_mapping": mapping,
            }
            session.add(
                StepEffect(
                    step_id=lease.step_id,
                    effect_type="INTEGRATE",
                    effect_json=effect_state,
                )
            )
        return self._save(lease, **effect_state)

    async def _summarize(self, lease) -> dict[str, Any]:
        state = self._state(lease)
        accepted = state.get("accepted_proposal_ids", [])
        mapping = state.get("proposal_canon_mapping", {})
        if not accepted:
            summary = {"facts": []}
        else:
            accepted_facts = [mapping[proposal_id] for proposal_id in accepted]
            output = await self._model_call(
                lease,
                task="research.summary",
                role_prompt=PROMPTS[StepKind.SUMMARIZE],
                payload={"accepted_facts": accepted_facts},
                output_type=SummaryOutput,
                evidence=self._evidence_items(state["fragment_ids"]),
                context_window=self.context_window,
            )
            valid_fragments = set(state["fragment_ids"])
            excerpts = {
                item.evidence_id: item.extract
                for item in self._evidence_items(state["fragment_ids"])
            }
            valid_revisions = {
                item["node_revision_id"]: item["node_id"] for item in accepted_facts
            }
            for fact in output.facts:
                if (
                    valid_revisions.get(fact.node_revision_id) != fact.node_id
                    or not set(fact.fragment_ids) <= valid_fragments
                ):
                    raise ValueError("summary cites content outside accepted canon")
                if not any(
                    fact.text in excerpts[fragment_id]
                    for fragment_id in fact.fragment_ids
                ):
                    raise ValueError("summary fact is not present in cited evidence")
            summary = output.model_dump(mode="json")
        with Session(self.engine) as session, session.begin():
            summary_id = self._workspace_id(lease.target_id)
            record = session.get(WorkflowSummary, summary_id)
            if record is None:
                session.add(
                    WorkflowSummary(
                        id=summary_id,
                        run_id=lease.run_id,
                        target_id=lease.target_id,
                        summary_json=summary,
                    )
                )
            else:
                record.summary_json = summary
        return self._save(lease, summary=summary)

    async def _complete(self, lease) -> dict[str, Any]:
        state = self._state(lease)
        accepted = state.get("accepted_proposal_ids", [])
        accepted_record_ids = state.get("accepted_record_ids", [])
        reused = bool(
            state.get("inventory", {}).get("accepted_node_ids")
        ) and not state.get("inventory", {}).get("missing_domains")
        requested_domains = tuple(
            self._scope(lease).get("domains") or policy_obligations(())
        )
        obligations = policy_obligations(
            requested_domains, self._policy("RESEARCH_COMPLETION")
        )
        freshness = self._freshness_scope(lease)
        required = {
            f"{domain}:{indicator}"
            for domain, obligation in obligations.items()
            for indicator in obligation["required_indicators"]
        }
        with Session(self.engine) as session:
            conflicts = session.scalar(
                select(func.count())
                .select_from(ClaimConflict)
                .where(
                    ClaimConflict.workspace_id == self._workspace_id(lease.target_id),
                    ClaimConflict.status != "RESOLVED",
                )
            )
            coverage_rows = session.scalars(
                select(CoverageRecord).where(
                    CoverageRecord.world_id == lease.world_id,
                    CoverageRecord.continuity
                    == str(self._scope(lease).get("continuity", "unspecified")),
                    CoverageRecord.era_or_timepoint == freshness["era_or_timepoint"],
                    CoverageRecord.branch_id == freshness["branch_id"],
                    CoverageRecord.conditions_key == freshness["conditions_key"],
                    CoverageRecord.domain.in_(requested_domains),
                )
            ).all()
            accepted_fields = session.scalars(
                select(MaterialProposalFieldRecord.name)
                .join(MaterialProposalRecord)
                .where(
                    MaterialProposalRecord.workspace_id
                    == self._workspace_id(lease.target_id)
                )
                .where(MaterialProposalRecord.id.in_(accepted_record_ids))
            ).all()
            provenance_rows = session.execute(
                select(
                    IntegrationEffect.proposal_id,
                    NodeEvidence.node_revision_id,
                    NodeEvidence.field_name,
                )
                .select_from(NodeEvidence)
                .join(CanonNodeRevision)
                .join(
                    IntegrationEffect,
                    IntegrationEffect.node_revision_id == CanonNodeRevision.id,
                )
                .where(IntegrationEffect.proposal_id.in_(accepted_record_ids))
            ).all()
            promotion_rows = session.scalars(
                select(IntegrationEffect.proposal_id).where(
                    IntegrationEffect.proposal_id.in_(accepted_record_ids)
                )
            ).all()
            unresolved_audits = (
                session.scalar(
                    select(func.count())
                    .select_from(AuditDecisionRecord)
                    .where(
                        AuditDecisionRecord.proposal_id.in_(accepted_record_ids),
                        AuditDecisionRecord.verdict.in_(
                            [
                                AuditVerdict.REVISE.value,
                                AuditVerdict.NEEDS_EVIDENCE.value,
                            ]
                        ),
                    )
                )
                or 0
            )
        accepted_indicators = {
            f"{row.domain}:{indicator}"
            for row in coverage_rows
            for indicator in row.indicators_json
        } & required
        accepted_field_count = len(
            {
                (proposal_id, field_name)
                for proposal_id, _revision_id, field_name in provenance_rows
            }
        )
        promotion_counts = {
            proposal_id: promotion_rows.count(proposal_id)
            for proposal_id in set(promotion_rows)
        }
        duplicate_promotions = sum(
            max(0, count - 1) for count in promotion_counts.values()
        )
        domain_coverage = {
            domain: (
                len(
                    {
                        indicator
                        for row in coverage_rows
                        if row.domain == domain
                        for indicator in row.indicators_json
                    }
                )
                / max(
                    1,
                    len(set(obligations[domain]["required_indicators"])),
                )
            )
            for domain in requested_domains
        }
        completion = evaluate_completion(
            CompletionInputs(
                required_indicators=frozenset(required),
                accepted_indicators=frozenset(accepted_indicators),
                critical_questions=frozenset(
                    f"{domain}:{question}"
                    for domain, obligation in obligations.items()
                    for question in obligation["critical_questions"]
                ),
                accepted_questions=frozenset(
                    f"{domain}:{question}"
                    for domain, obligation in obligations.items()
                    if {
                        f"{domain}:{indicator}"
                        for indicator in obligation["required_indicators"]
                    }
                    <= accepted_indicators
                    for question in obligation["critical_questions"]
                ),
                allowed_gap_questions=frozenset(
                    state.get("allowed_gap_question_ids", ())
                ),
                provenance_rate=(
                    1.0
                    if not accepted_record_ids
                    else min(1.0, accepted_field_count / len(accepted_fields))
                    if accepted_fields
                    else 0.0
                ),
                domain_coverage=domain_coverage,
                unresolved_invalidating_conflicts=int(conflicts or 0),
                unresolved_audit_decisions=int(unresolved_audits),
                duplicate_promotions=duplicate_promotions,
            )
        )
        outcome = completion.outcome if (accepted or reused) else RunOutcome.PARTIAL
        loop_count = int(state.get("loop_count", 0))
        actionable = bool(state.get("inventory", {}).get("missing_domains"))
        if (
            outcome is RunOutcome.PARTIAL
            and actionable
            and loop_count < self.max_gap_loops
        ):
            next_loop = loop_count + 1
            for kind in list(StepKind)[1:]:
                self.kernel.append_step(
                    lease.run_id,
                    lease.target_id,
                    kind,
                    f"gap-loop:{lease.target_id}:{next_loop}:{kind.value}",
                )
            return self._save(
                lease,
                loop_count=next_loop,
                continue_loop=True,
                accepted_proposal_ids=[],
                accepted_record_ids=[],
            )
        if outcome is RunOutcome.PARTIAL:
            gap_id = _stable("gap", lease.target_id, "insufficient-evidence")
            with Session(self.engine) as session, session.begin():
                if session.get(ResearchGapRecord, gap_id) is None:
                    session.add(
                        ResearchGapRecord(
                            id=gap_id,
                            workspace_id=self._workspace_id(lease.target_id),
                            gap_json={
                                "reason": "INSUFFICIENT_EVIDENCE",
                                "loop_cap": self.max_gap_loops,
                                "reasons": list(completion.reasons),
                            },
                        )
                    )
        return self._save(lease, outcome=outcome.value, continue_loop=False)
