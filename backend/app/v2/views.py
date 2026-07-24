from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.v2.contracts import CreateResearchRun, ResearchRunTargetInput
from app.v2.models import (
    AuditDecisionRecord,
    CandidateHealth,
    CanonNode,
    CanonNodeRevision,
    Checkpoint,
    ClaimConflict,
    CredentialHealth,
    CredentialRef,
    EvidenceFragment,
    MaterialProposalFieldRecord,
    MaterialProposalRecord,
    ModelCall,
    NodeEvidence,
    OutboxEvent,
    PromotionDecision,
    Provider,
    ProviderModel,
    ResearchGapRecord,
    ResearchWorkspace,
    Route,
    RouteCandidate,
    Run,
    RunTarget,
    Source,
    SourceRevision,
    ToolEvent,
    WorkflowSummary,
    World,
)
from app.v2.research_runs import (
    IdempotencyConflictError,
    IllegalTransitionError,
    RunNotFoundError,
)
from app.v2.workflow import policy_obligations

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
TERMINAL_STATUSES = {"CANCELLED", "FAILED", "SUCCEEDED"}


def _runtime(request: Request):
    return request.app.state.runtime


def _context(request: Request, **values: object) -> dict[str, object]:
    return {"request": request, "current_path": request.url.path, **values}


def _worlds(request: Request, q: str = "", cursor: str | None = None, limit: int = 25):
    with Session(_runtime(request).engine) as session:
        statement = select(World)
        if q:
            pattern = f"%{q}%"
            statement = statement.where(
                or_(
                    World.id.ilike(pattern),
                    World.name.ilike(pattern),
                    World.franchise.ilike(pattern),
                    World.category.ilike(pattern),
                )
            )
        if cursor:
            statement = statement.where(World.id > cursor)
        rows = session.scalars(statement.order_by(World.id).limit(limit + 1)).all()
    return {
        "items": [
            {
                "id": row.id,
                "name": row.name,
                "franchise": row.franchise,
                "category": row.category,
                "continuity": row.continuity,
            }
            for row in rows[:limit]
        ],
        "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
        "q": q,
    }


def _run_projection(request: Request, run_id: str) -> dict[str, object]:
    projection = _runtime(request).research_kernel.get(run_id)
    return projection.model_dump(mode="json")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "pages/index.html", _context(request))


@router.get("/research/", response_class=HTMLResponse)
def research(request: Request):
    return templates.TemplateResponse(
        request,
        "pages/research.html",
        _context(
            request,
            worlds=_worlds(request),
            research_domains=tuple(policy_obligations(())),
        ),
    )


@router.get("/research/worlds", response_class=HTMLResponse)
def research_worlds(
    request: Request,
    q: str = "",
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
):
    return templates.TemplateResponse(
        request,
        "v2/research_worlds.html",
        _context(request, worlds=_worlds(request, q, cursor, limit)),
    )


@router.post("/research/runs", response_class=HTMLResponse, status_code=202)
def create_run(
    request: Request,
    world_ids: Annotated[list[str], Form()],
    objective: Annotated[str, Form(min_length=1)],
    idempotency_key: Annotated[str, Form(min_length=1)],
    continuity: Annotated[str, Form()] = "primary",
    domains: Annotated[list[str] | None, Form()] = None,
):
    unique_world_ids = tuple(dict.fromkeys(world_ids))
    if not unique_world_ids:
        raise HTTPException(status_code=422, detail="select at least one world")
    scope = {
        "continuity": continuity,
        "domains": domains or list(policy_obligations(())),
    }
    command = CreateResearchRun(
        objective=objective,
        scope=scope,
        targets=tuple(
            ResearchRunTargetInput(world_id=world_id, objective=objective, scope=scope)
            for world_id in unique_world_ids
        ),
    )
    try:
        projection = _runtime(request).research_kernel.create(command, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    response = templates.TemplateResponse(
        request,
        "v2/research_run.html",
        _context(request, run=projection.model_dump(mode="json")),
        status_code=202,
    )
    response.headers["HX-Retarget"] = "#run-queue"
    response.headers["HX-Reswap"] = "afterbegin"
    response.headers["X-Run-ID"] = projection.id
    return response


@router.get("/research/runs", response_class=HTMLResponse)
def run_queue(request: Request):
    with Session(_runtime(request).engine) as session:
        ids = list(session.scalars(select(Run.id).order_by(Run.created_at.desc())))
    runs = [_run_projection(request, run_id) for run_id in ids]
    return templates.TemplateResponse(
        request, "v2/research_queue.html", _context(request, runs=runs)
    )


@router.get("/research/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: str):
    try:
        run = _run_projection(request, run_id)
    except RunNotFoundError as error:
        raise HTTPException(status_code=404, detail="run not found") from error
    return templates.TemplateResponse(
        request, "v2/research_run.html", _context(request, run=run)
    )


def _run_action(request: Request, run_id: str, action: str):
    kernel = _runtime(request).research_kernel
    try:
        projection = (
            kernel.request_cancel(run_id, datetime.now(timezone.utc))
            if action == "cancel"
            else kernel.retry(run_id, datetime.now(timezone.utc))
        )
    except RunNotFoundError as error:
        raise HTTPException(status_code=404, detail="run not found") from error
    except IllegalTransitionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return templates.TemplateResponse(
        request,
        "v2/research_run.html",
        _context(request, run=projection.model_dump(mode="json")),
    )


@router.post("/research/runs/{run_id}/cancel", response_class=HTMLResponse)
def cancel_run(request: Request, run_id: str):
    return _run_action(request, run_id, "cancel")


@router.post("/research/runs/{run_id}/retry", response_class=HTMLResponse)
def retry_run(request: Request, run_id: str):
    return _run_action(request, run_id, "retry")


@router.get("/theory/", response_class=HTMLResponse)
def theory(request: Request):
    return templates.TemplateResponse(request, "pages/theory.html", _context(request))


def _world_dict(row: World) -> dict[str, object]:
    return {"id": row.id, "name": row.name, "franchise": row.franchise}


@router.get("/knowledge/", response_class=HTMLResponse)
def knowledge(request: Request, world_id: str | None = None, q: str = ""):
    listing = _worlds(request, q)
    selected = next(
        (world for world in listing["items"] if world["id"] == world_id), None
    )
    if world_id and selected is None:
        with Session(_runtime(request).engine) as session:
            row = session.get(World, world_id)
            selected = _world_dict(row) if row else None
    return templates.TemplateResponse(
        request,
        "pages/knowledge.html",
        _context(request, worlds=listing, selected_world=selected),
    )


@router.get("/knowledge/{world_id}/{tab}", response_class=HTMLResponse)
def knowledge_tab(request: Request, world_id: str, tab: str):
    if tab not in {"overview", "canon", "evidence", "gaps"}:
        raise HTTPException(status_code=404, detail="knowledge tab not found")
    runtime = _runtime(request)
    with Session(runtime.engine) as session:
        world = session.get(World, world_id)
        if world is None:
            raise HTTPException(status_code=404, detail="world not found")
        workspace_ids = list(
            session.scalars(
                select(ResearchWorkspace.id).where(
                    ResearchWorkspace.world_id == world_id
                )
            )
        )
        run_ids = list(
            session.scalars(
                select(ResearchWorkspace.run_id).where(
                    ResearchWorkspace.world_id == world_id
                )
            )
        )
        summaries = (
            [
                dict(row.summary_json)
                for row in session.scalars(
                    select(WorkflowSummary).where(WorkflowSummary.run_id.in_(run_ids))
                )
            ]
            if run_ids
            else []
        )
        gaps = (
            [
                {"id": row.id, **dict(row.gap_json)}
                for row in session.scalars(
                    select(ResearchGapRecord).where(
                        ResearchGapRecord.workspace_id.in_(workspace_ids)
                    )
                )
            ]
            if workspace_ids
            else []
        )
        conflicts = (
            [
                {"id": row.id, "status": row.status, "resolution": row.resolution_json}
                for row in session.scalars(
                    select(ClaimConflict).where(
                        ClaimConflict.workspace_id.in_(workspace_ids)
                    )
                )
            ]
            if workspace_ids
            else []
        )
        evidence = [
            {
                "id": row.id,
                "exact_excerpt": row.exact_excerpt,
                "domain": row.domain,
                "source_revision_id": row.source_revision_id,
            }
            for row in session.scalars(
                select(EvidenceFragment)
                .where(EvidenceFragment.world_id == world_id)
                .order_by(EvidenceFragment.id)
            )
        ]
    canon = list(runtime.query_service.accepted_graph(world_id))
    coverage = []
    continuities = {str(item["scope"].get("continuity", "")) for item in canon}
    for continuity in continuities:
        coverage.extend(runtime.query_service.coverage(world_id, continuity))
    return templates.TemplateResponse(
        request,
        f"v2/knowledge_{tab}.html",
        _context(
            request,
            world=_world_dict(world),
            canon=canon,
            coverage=coverage,
            summaries=summaries,
            evidence=evidence,
            gaps=gaps,
            conflicts=conflicts,
        ),
    )


@router.get("/provenance/{node_id}", response_class=HTMLResponse)
def provenance(request: Request, node_id: str):
    with Session(_runtime(request).engine) as session:
        node = session.get(CanonNode, node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="canon node not found")
        rows = session.execute(
            select(
                CanonNodeRevision,
                NodeEvidence,
                EvidenceFragment,
                SourceRevision,
                Source,
            )
            .outerjoin(
                NodeEvidence, NodeEvidence.node_revision_id == CanonNodeRevision.id
            )
            .outerjoin(
                EvidenceFragment,
                EvidenceFragment.id == NodeEvidence.evidence_fragment_id,
            )
            .outerjoin(
                SourceRevision,
                SourceRevision.id == EvidenceFragment.source_revision_id,
            )
            .outerjoin(Source, Source.id == SourceRevision.source_id)
            .where(CanonNodeRevision.node_id == node_id)
            .order_by(CanonNodeRevision.revision_number.desc())
        ).all()
    chain = [
        {
            "revision_id": revision.id,
            "revision_number": revision.revision_number,
            "fields": dict(revision.fields_json),
            "field_name": link.field_name if link else None,
            "fragment_id": fragment.id if fragment else None,
            "exact_excerpt": fragment.exact_excerpt if fragment else None,
            "source_revision_id": source_revision.id if source_revision else None,
            "canonical_url": source.canonical_url if source else None,
        }
        for revision, link, fragment, source_revision, source in rows
    ]
    return templates.TemplateResponse(
        request,
        "pages/provenance.html",
        _context(request, node={"id": node.id, "kind": node.kind}, chain=chain),
    )


@router.get("/validation/", response_class=HTMLResponse)
def validation(request: Request):
    with Session(_runtime(request).engine) as session:
        rows = session.execute(
            select(
                AuditDecisionRecord,
                MaterialProposalRecord,
                MaterialProposalFieldRecord,
            )
            .join(
                MaterialProposalRecord,
                MaterialProposalRecord.id == AuditDecisionRecord.proposal_id,
            )
            .outerjoin(
                MaterialProposalFieldRecord,
                (MaterialProposalFieldRecord.proposal_id == MaterialProposalRecord.id)
                & (MaterialProposalFieldRecord.name == AuditDecisionRecord.field_name),
            )
            .order_by(AuditDecisionRecord.id)
        ).all()
        audits = [
            {
                "id": audit.id,
                "proposal_id": proposal.id,
                "field_name": audit.field_name,
                "value": field.value_json if field else None,
                "verdict": audit.verdict,
                "reason_code": audit.reason_code,
                "evidence_ids": tuple(audit.evidence_fragment_ids_json),
            }
            for audit, proposal, field in rows
        ]
        promotions = [
            {"id": row.id, "proposal_id": row.proposal_id, "decision": row.decision}
            for row in session.scalars(
                select(PromotionDecision).order_by(PromotionDecision.id)
            )
        ]
        conflicts = [
            {"id": row.id, "status": row.status}
            for row in session.scalars(select(ClaimConflict).order_by(ClaimConflict.id))
        ]
    return templates.TemplateResponse(
        request,
        "pages/validation.html",
        _context(request, audits=audits, promotions=promotions, conflicts=conflicts),
    )


@router.post(
    "/validation/audits/{audit_id}/follow-up",
    response_class=HTMLResponse,
    status_code=202,
)
def validation_follow_up(request: Request, audit_id: str):
    with Session(_runtime(request).engine) as session:
        row = session.execute(
            select(AuditDecisionRecord, MaterialProposalRecord, ResearchWorkspace)
            .join(
                MaterialProposalRecord,
                MaterialProposalRecord.id == AuditDecisionRecord.proposal_id,
            )
            .join(
                ResearchWorkspace,
                ResearchWorkspace.id == MaterialProposalRecord.workspace_id,
            )
            .where(AuditDecisionRecord.id == audit_id)
        ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="audit decision not found")
    audit, proposal, workspace = row
    if audit.verdict not in {"NEEDS_EVIDENCE", "REVISE", "CONTRADICTED"}:
        raise HTTPException(status_code=409, detail="audit does not require follow-up")
    objective = (
        f"Resolve {audit.verdict} for proposal {proposal.id} field "
        f"{audit.field_name}: {audit.reason_code}"
    )
    scope = {
        "continuity": workspace.continuity,
        "audit_id": audit.id,
        "proposal_id": proposal.id,
    }
    command = CreateResearchRun(
        objective=objective,
        scope=scope,
        targets=(
            ResearchRunTargetInput(
                world_id=workspace.world_id,
                objective=objective,
                scope=scope,
            ),
        ),
    )
    projection = _runtime(request).research_kernel.create(
        command, f"validation-follow-up:{audit.id}"
    )
    response = templates.TemplateResponse(
        request,
        "v2/research_run.html",
        _context(request, run=projection.model_dump(mode="json")),
        status_code=202,
    )
    response.headers["X-Run-ID"] = projection.id
    return response


def _flow(request: Request, run_id: str) -> dict[str, object]:
    projection = _run_projection(request, run_id)
    with Session(_runtime(request).engine) as session:
        step_ids = [step["id"] for step in projection["steps"]]
        checkpoints = (
            [
                {
                    "kind": "CHECKPOINT",
                    "id": row.id,
                    "step_id": row.step_id,
                    "created_at": row.created_at,
                }
                for row in session.scalars(
                    select(Checkpoint)
                    .where(Checkpoint.step_id.in_(step_ids))
                    .order_by(Checkpoint.created_at, Checkpoint.id)
                )
            ]
            if step_ids
            else []
        )
        tools = (
            [
                {
                    "kind": "TOOL",
                    "id": row.id,
                    "step_id": row.step_id,
                    "status": row.status,
                    "created_at": row.created_at,
                }
                for row in session.scalars(
                    select(ToolEvent)
                    .where(ToolEvent.step_id.in_(step_ids))
                    .order_by(ToolEvent.created_at, ToolEvent.id)
                )
            ]
            if step_ids
            else []
        )
        calls = (
            [
                {
                    "kind": "MODEL_CALL",
                    "id": row.id,
                    "step_id": row.step_id,
                    "status": row.task,
                    "created_at": None,
                }
                for row in session.scalars(
                    select(ModelCall)
                    .where(ModelCall.step_id.in_(step_ids))
                    .order_by(ModelCall.id)
                )
            ]
            if step_ids
            else []
        )
        events = [
            {
                "kind": "EVENT",
                "id": row.id,
                "event_type": row.event_type,
                "payload": dict(row.payload_json),
                "created_at": row.created_at,
            }
            for row in session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.run_id == run_id)
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
            )
        ]
    return {
        "run": projection,
        "checkpoints": checkpoints,
        "tools": tools,
        "calls": calls,
        "events": events,
    }


@router.get("/flow/", response_class=HTMLResponse)
def flow_index(request: Request):
    with Session(_runtime(request).engine) as session:
        runs = [
            {"id": row.id, "status": row.status, "objective": row.objective}
            for row in session.scalars(
                select(Run).order_by(Run.created_at.desc(), Run.id)
            )
        ]
    return templates.TemplateResponse(
        request, "pages/flow.html", _context(request, runs=runs, flow=None)
    )


@router.get("/flow/{run_id}", response_class=HTMLResponse)
def flow_detail(request: Request, run_id: str):
    try:
        value = _flow(request, run_id)
    except RunNotFoundError as error:
        raise HTTPException(status_code=404, detail="run not found") from error
    return templates.TemplateResponse(
        request, "pages/flow.html", _context(request, runs=[], flow=value)
    )


@router.get("/logs/", response_class=HTMLResponse)
def logs(
    request: Request,
    run_id: str = "",
    world_id: str = "",
    status: str = "",
    event_type: str = "",
    cursor: str | None = None,
):
    with Session(_runtime(request).engine) as session:
        run_statement = select(Run)
        if run_id:
            run_statement = run_statement.where(Run.id == run_id)
        if status:
            run_statement = run_statement.where(Run.status == status)
        if world_id:
            run_statement = run_statement.where(
                Run.id.in_(
                    select(RunTarget.run_id).where(RunTarget.world_id == world_id)
                )
            )
        runs = [
            {"id": row.id, "status": row.status, "objective": row.objective}
            for row in session.scalars(
                run_statement.order_by(Run.created_at.desc(), Run.id)
            )
        ]
        event_statement = select(OutboxEvent)
        if run_id:
            event_statement = event_statement.where(OutboxEvent.run_id == run_id)
        if event_type:
            event_statement = event_statement.where(
                OutboxEvent.event_type == event_type
            )
        if world_id or status:
            event_statement = event_statement.where(
                OutboxEvent.run_id.in_([run["id"] for run in runs])
            )
        if cursor:
            cursor_event = session.get(OutboxEvent, cursor)
            if cursor_event is None:
                raise HTTPException(status_code=400, detail="invalid event cursor")
            event_statement = event_statement.where(
                or_(
                    OutboxEvent.created_at < cursor_event.created_at,
                    and_(
                        OutboxEvent.created_at == cursor_event.created_at,
                        OutboxEvent.id > cursor_event.id,
                    ),
                )
            )
        events = [
            {
                "id": row.id,
                "run_id": row.run_id,
                "event_type": row.event_type,
                "payload": json.dumps(row.payload_json, sort_keys=True),
                "created_at": row.created_at,
            }
            for row in session.scalars(
                event_statement.order_by(
                    OutboxEvent.created_at.desc(), OutboxEvent.id
                ).limit(101)
            )
        ]
    next_cursor = events[99]["id"] if len(events) > 100 else None
    next_url = None
    if next_cursor:
        query = {
            key: value
            for key, value in {
                "run_id": run_id,
                "world_id": world_id,
                "status": status,
                "event_type": event_type,
                "cursor": next_cursor,
            }.items()
            if value
        }
        next_url = f"/logs/?{urlencode(query)}"
    return templates.TemplateResponse(
        request,
        "pages/logs.html",
        _context(
            request,
            runs=runs,
            events=events[:100],
            filters={
                "run_id": run_id,
                "world_id": world_id,
                "status": status,
                "event_type": event_type,
            },
            next_cursor=next_cursor,
            next_url=next_url,
        ),
    )


def _settings_projection(request: Request) -> dict[str, object]:
    with Session(_runtime(request).engine) as session:
        providers = session.scalars(select(Provider).order_by(Provider.id)).all()
        return {
            "providers": [
                {
                    "id": provider.id,
                    "kind": provider.kind,
                    "base_url": provider.base_url,
                    "active": provider.active,
                    "models": [
                        {
                            "id": model.id,
                            "name": model.model_name,
                            "supports_tools": model.supports_tools,
                            "supports_structured": model.supports_structured,
                        }
                        for model in session.scalars(
                            select(ProviderModel)
                            .where(ProviderModel.provider_id == provider.id)
                            .order_by(ProviderModel.id)
                        )
                    ],
                    "credentials": [
                        {
                            "credential_id": credential.id,
                            "label": credential.label,
                            "weight": credential.weight,
                            "mask": "********",
                        }
                        for credential in session.scalars(
                            select(CredentialRef)
                            .where(CredentialRef.provider_id == provider.id)
                            .order_by(CredentialRef.id)
                        )
                    ],
                }
                for provider in providers
            ],
            "routes": [
                {
                    "route_id": route.id,
                    "task": route.task,
                    "candidate_id": candidate.id,
                    "model_id": candidate.model_id,
                    "position": candidate.position,
                    "weight": candidate.weight,
                }
                for candidate, route in session.execute(
                    select(RouteCandidate, Route)
                    .join(Route)
                    .order_by(Route.position, Route.task, RouteCandidate.position)
                )
            ],
        }


@router.get("/settings/", response_class=HTMLResponse)
def settings(request: Request):
    return templates.TemplateResponse(request, "pages/settings.html", _context(request))


@router.get("/settings/tab/{tab}", response_class=HTMLResponse)
def settings_tab(request: Request, tab: str):
    if tab not in {"general", "providers", "models", "routes", "health"}:
        raise HTTPException(status_code=404, detail="settings tab not found")
    data = _settings_projection(request)
    return templates.TemplateResponse(
        request,
        f"v2/settings_{tab}.html",
        _context(
            request,
            settings=data,
            config=_runtime(request).config,
            adapter_status=_runtime(request).adapter_status,
            worker_running=bool(_runtime(request).worker._tasks)
            and not all(task.done() for task in _runtime(request).worker._tasks),
        ),
    )


@router.post("/settings/providers", response_class=HTMLResponse, status_code=201)
def settings_create_provider(
    request: Request,
    provider_id: Annotated[str, Form()],
    kind: Annotated[str, Form()],
    base_url: Annotated[str, Form()] = "",
):
    with Session(_runtime(request).engine) as session, session.begin():
        if session.get(Provider, provider_id):
            raise HTTPException(status_code=409, detail="provider already exists")
        session.add(
            Provider(id=provider_id, kind=kind, base_url=base_url or None, active=True)
        )
    return settings_tab(request, "providers")


@router.post("/settings/providers/{provider_id}", response_class=HTMLResponse)
def settings_update_provider(
    request: Request,
    provider_id: str,
    base_url: Annotated[str, Form()] = "",
    active: Annotated[bool, Form()] = False,
):
    with Session(_runtime(request).engine) as session, session.begin():
        provider = session.get(Provider, provider_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="provider not found")
        provider.base_url = base_url or None
        provider.active = active
    _runtime(request).provider_router.refresh_adapters(
        _runtime(request).http_client,
        timeout_seconds=_runtime(request).config.http_timeout_seconds,
    )
    return settings_tab(request, "providers")


@router.post(
    "/settings/providers/{provider_id}/models/{model_id}",
    response_class=HTMLResponse,
)
def settings_put_model(
    request: Request,
    provider_id: str,
    model_id: str,
    model_name: Annotated[str, Form()],
    context_window: Annotated[int | None, Form()] = None,
    output_limit: Annotated[int | None, Form()] = None,
    supports_tools: Annotated[bool, Form()] = False,
    supports_structured: Annotated[bool, Form()] = False,
    supports_text: Annotated[bool, Form()] = True,
    active: Annotated[bool, Form()] = True,
):
    with Session(_runtime(request).engine) as session, session.begin():
        if session.get(Provider, provider_id) is None:
            raise HTTPException(status_code=404, detail="provider not found")
        model = session.get(ProviderModel, model_id)
        if model is None:
            model = ProviderModel(
                id=model_id, provider_id=provider_id, model_name=model_name
            )
            session.add(model)
        elif model.provider_id != provider_id:
            raise HTTPException(
                status_code=409, detail="model belongs to another provider"
            )
        model.model_name = model_name
        model.context_window = context_window
        model.output_limit = output_limit
        model.supports_tools = supports_tools
        model.supports_structured = supports_structured
        model.supports_text = supports_text
        model.active = active
    _runtime(request).provider_router.refresh_adapters(
        _runtime(request).http_client,
        timeout_seconds=_runtime(request).config.http_timeout_seconds,
    )
    return settings_tab(request, "models")


@router.post(
    "/settings/providers/{provider_id}/models",
    response_class=HTMLResponse,
)
def settings_put_model_form(
    request: Request,
    provider_id: str,
    model_id: Annotated[str, Form()],
    model_name: Annotated[str, Form()],
    context_window: Annotated[int | None, Form()] = None,
    output_limit: Annotated[int | None, Form()] = None,
    supports_tools: Annotated[bool, Form()] = False,
    supports_structured: Annotated[bool, Form()] = False,
    supports_text: Annotated[bool, Form()] = True,
    active: Annotated[bool, Form()] = True,
):
    return settings_put_model(
        request,
        provider_id,
        model_id,
        model_name,
        context_window,
        output_limit,
        supports_tools,
        supports_structured,
        supports_text,
        active,
    )


@router.post("/settings/routes/{task}", response_class=HTMLResponse)
def settings_put_route(
    request: Request,
    task: str,
    model_ids: Annotated[list[str], Form()],
    weights: Annotated[list[int] | None, Form()] = None,
):
    unique_model_ids = tuple(dict.fromkeys(model_ids))
    if not unique_model_ids:
        raise HTTPException(status_code=422, detail="route requires a model")
    route_id = f"route:{task}"
    with Session(_runtime(request).engine) as session, session.begin():
        for model_id in unique_model_ids:
            if session.get(ProviderModel, model_id) is None:
                raise HTTPException(
                    status_code=404, detail=f"model {model_id} not found"
                )
        route = session.scalar(select(Route).where(Route.task == task))
        if route is None:
            route = Route(id=route_id, task=task, position=0, active=True)
            session.add(route)
            session.flush()
        else:
            route_id = route.id
            candidate_ids = list(
                session.scalars(
                    select(RouteCandidate.id).where(RouteCandidate.route_id == route.id)
                )
            )
            if candidate_ids:
                session.execute(
                    delete(CandidateHealth).where(
                        CandidateHealth.candidate_id.in_(candidate_ids)
                    )
                )
            session.execute(
                delete(RouteCandidate).where(RouteCandidate.route_id == route.id)
            )
        for position, model_id in enumerate(unique_model_ids):
            weight = weights[position] if weights and position < len(weights) else 1
            session.add(
                RouteCandidate(
                    id=f"candidate:{route_id}:{position}",
                    route_id=route_id,
                    model_id=model_id,
                    position=position,
                    weight=max(weight, 1),
                )
            )
    return settings_tab(request, "routes")


@router.post("/settings/routes", response_class=HTMLResponse)
def settings_put_route_form(
    request: Request,
    task: Annotated[str, Form()],
    model_ids: Annotated[list[str], Form()],
    weights: Annotated[list[int] | None, Form()] = None,
):
    return settings_put_route(request, task, model_ids, weights)


@router.post(
    "/settings/providers/{provider_id}/credentials",
    response_class=HTMLResponse,
    status_code=201,
)
def settings_add_credential(
    request: Request,
    provider_id: str,
    label: Annotated[str, Form()],
    secret: Annotated[str, Form()],
    weight: Annotated[int, Form()] = 1,
):
    with Session(_runtime(request).engine) as session:
        if session.get(Provider, provider_id) is None:
            raise HTTPException(status_code=404, detail="provider not found")
    metadata = _runtime(request).credentials.add(
        provider_id, label, secret, weight=weight
    )
    response = templates.TemplateResponse(
        request,
        "v2/settings_credential.html",
        _context(
            request,
            provider_id=provider_id,
            credential={
                "credential_id": metadata.credential_id,
                "label": metadata.label,
                "weight": weight,
                "mask": "********",
            },
        ),
        status_code=201,
    )
    response.headers["X-Credential-ID"] = metadata.credential_id
    return response


@router.delete(
    "/settings/providers/{provider_id}/credentials/{credential_id}",
    response_class=HTMLResponse,
)
def settings_delete_credential(request: Request, provider_id: str, credential_id: str):
    with Session(_runtime(request).engine) as session:
        row = session.get(CredentialRef, credential_id)
        if row is None or row.provider_id != provider_id:
            raise HTTPException(status_code=404, detail="credential not found")
    _runtime(request).credentials.delete(credential_id)
    return HTMLResponse('<p class="text-xs text-gray-500">Credential deleted.</p>')


@router.post(
    "/settings/health/credentials/{credential_id}/reset", response_class=HTMLResponse
)
def settings_reset_credential(request: Request, credential_id: str):
    with Session(_runtime(request).engine) as session, session.begin():
        if session.get(CredentialRef, credential_id) is None:
            raise HTTPException(status_code=404, detail="credential not found")
        health = session.get(CredentialHealth, credential_id)
        if health is None:
            session.add(CredentialHealth(credential_id=credential_id))
        else:
            health.cooldown_until = None
            health.disabled = False
            health.failure_count = 0
            health.last_error_class = None
    return HTMLResponse('<span class="text-green-600">Healthy</span>')


@router.post(
    "/settings/health/candidates/{candidate_id}/reset", response_class=HTMLResponse
)
def settings_reset_candidate(request: Request, candidate_id: str):
    with Session(_runtime(request).engine) as session, session.begin():
        if session.get(RouteCandidate, candidate_id) is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        session.execute(
            delete(CandidateHealth).where(CandidateHealth.candidate_id == candidate_id)
        )
    return HTMLResponse('<span class="text-green-600">Healthy</span>')


@router.get("/worlds")
@router.get("/worlds/")
@router.get("/research/choose-world")
def deprecated_worlds() -> RedirectResponse:
    return RedirectResponse("/research/", status_code=307)
