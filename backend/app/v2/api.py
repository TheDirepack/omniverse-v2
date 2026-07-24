from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import Engine, delete, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.v2.contracts import CreateResearchRun
from app.v2.credentials import CredentialService, JsonCredentialStore
from app.v2.models import (
    CandidateHealth,
    CredentialHealth,
    CredentialRef,
    EvidenceFragment,
    Provider,
    ProviderModel,
    Route,
    RouteCandidate,
    Run,
    World,
)
from app.v2.projections import ResearchQueryService
from app.v2.research_runs import (
    IdempotencyConflictError,
    IllegalTransitionError,
    ResearchRunKernel,
    RunNotFoundError,
)


class CredentialCreate(BaseModel):
    label: str = Field(min_length=1)
    secret: str = Field(min_length=1, repr=False)
    weight: int = Field(default=1, ge=1)


class ProviderCreate(BaseModel):
    id: str = Field(min_length=1)
    kind: str = Field(pattern="^(OPENAI|GEMINI|OPENAI_COMPATIBLE)$")
    base_url: str | None = None
    active: bool = True


class ProviderUpdate(BaseModel):
    base_url: str | None = None
    active: bool | None = None


class ModelUpdate(BaseModel):
    model_name: str = Field(min_length=1)
    context_window: int | None = Field(default=None, gt=0)
    output_limit: int | None = Field(default=None, gt=0)
    supports_tools: bool = False
    supports_structured: bool = False
    supports_text: bool = True
    active: bool = True


class RouteCandidateInput(BaseModel):
    model_id: str = Field(min_length=1)
    weight: int = Field(default=1, ge=1)


class RouteUpdate(BaseModel):
    candidates: list[RouteCandidateInput]
    active: bool = True


def build_router(engine: Engine | object, credentials_path=None) -> APIRouter:
    runtime = engine if hasattr(engine, "research_kernel") else None
    if runtime is not None:
        engine = runtime.engine
        credentials_path = runtime.config.credentials_path
    router = APIRouter(prefix="/api/v2")
    kernel = (
        runtime.research_kernel if runtime is not None else ResearchRunKernel(engine)
    )
    queries = (
        runtime.query_service if runtime is not None else ResearchQueryService(engine)
    )
    credential_service = (
        CredentialService(JsonCredentialStore(credentials_path), engine)
        if credentials_path is not None
        else None
    )

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/worlds")
    def worlds(
        q: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, object]:
        try:
            with Session(engine) as session:
                statement = select(World)
                if q:
                    pattern = f"%{q}%"
                    statement = statement.where(
                        or_(
                            World.id.ilike(pattern),
                            World.name.ilike(pattern),
                            World.franchise.ilike(pattern),
                        )
                    )
                if cursor:
                    statement = statement.where(World.id > cursor)
                rows = session.scalars(
                    statement.order_by(World.id).limit(limit + 1)
                ).all()
        except OperationalError as error:
            raise HTTPException(
                status_code=503, detail="schema is not initialized"
            ) from error
        return {
            "items": [
                {"id": row.id, "name": row.name, "parent_id": row.parent_id}
                for row in rows[:limit]
            ],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
        }

    def refresh_adapters() -> None:
        if runtime is not None:
            runtime.provider_router.refresh_adapters(
                runtime.http_client,
                timeout_seconds=runtime.config.http_timeout_seconds,
            )

    @router.post("/providers", status_code=201)
    def create_provider(command: ProviderCreate) -> dict[str, object]:
        with Session(engine) as session, session.begin():
            if session.get(Provider, command.id) is not None:
                raise HTTPException(status_code=409, detail="provider already exists")
            row = Provider(**command.model_dump())
            session.add(row)
        refresh_adapters()
        return command.model_dump()

    @router.patch("/providers/{provider_id}")
    def update_provider(provider_id: str, command: ProviderUpdate) -> dict[str, object]:
        with Session(engine) as session, session.begin():
            row = session.get(Provider, provider_id)
            if row is None:
                raise HTTPException(status_code=404, detail="provider not found")
            for key, value in command.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            result = {
                "id": row.id,
                "kind": row.kind,
                "base_url": row.base_url,
                "active": row.active,
            }
        refresh_adapters()
        return result

    @router.delete("/providers/{provider_id}", status_code=204)
    def delete_provider(provider_id: str) -> Response:
        with Session(engine) as session, session.begin():
            provider = session.get(Provider, provider_id)
            if provider is None:
                raise HTTPException(status_code=404, detail="provider not found")
            model_ids = list(
                session.scalars(
                    select(ProviderModel.id).where(
                        ProviderModel.provider_id == provider_id
                    )
                )
            )
            candidate_ids = (
                list(
                    session.scalars(
                        select(RouteCandidate.id).where(
                            RouteCandidate.model_id.in_(model_ids)
                        )
                    )
                )
                if model_ids
                else []
            )
            credential_ids = list(
                session.scalars(
                    select(CredentialRef.id).where(
                        CredentialRef.provider_id == provider_id
                    )
                )
            )
            credential_refs = list(
                session.scalars(
                    select(CredentialRef.opaque_ref).where(
                        CredentialRef.provider_id == provider_id
                    )
                )
            )
            if candidate_ids:
                session.execute(
                    delete(CandidateHealth).where(
                        CandidateHealth.candidate_id.in_(candidate_ids)
                    )
                )
                session.execute(
                    delete(RouteCandidate).where(RouteCandidate.id.in_(candidate_ids))
                )
            if credential_ids:
                session.execute(
                    delete(CredentialHealth).where(
                        CredentialHealth.credential_id.in_(credential_ids)
                    )
                )
                session.execute(
                    delete(CredentialRef).where(CredentialRef.id.in_(credential_ids))
                )
            session.execute(
                delete(ProviderModel).where(ProviderModel.provider_id == provider_id)
            )
            session.delete(provider)
        if credential_service is not None:
            for opaque_ref in credential_refs:
                if not opaque_ref.startswith("env:"):
                    credential_service.store.delete(opaque_ref)
        refresh_adapters()
        return Response(status_code=204)

    @router.put("/providers/{provider_id}/models/{model_id}")
    def put_model(
        provider_id: str, model_id: str, command: ModelUpdate
    ) -> dict[str, object]:
        with Session(engine) as session, session.begin():
            if session.get(Provider, provider_id) is None:
                raise HTTPException(status_code=404, detail="provider not found")
            row = session.get(ProviderModel, model_id)
            values = command.model_dump()
            if row is None:
                row = ProviderModel(id=model_id, provider_id=provider_id, **values)
                session.add(row)
            elif row.provider_id != provider_id:
                raise HTTPException(
                    status_code=409, detail="model belongs to another provider"
                )
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        return {"id": model_id, "provider_id": provider_id, **values}

    @router.put("/routes/{task}")
    def put_route(task: str, command: RouteUpdate) -> dict[str, object]:
        route_id = f"route:{task}"
        with Session(engine) as session, session.begin():
            for candidate in command.candidates:
                if session.get(ProviderModel, candidate.model_id) is None:
                    raise HTTPException(
                        status_code=404, detail=f"model {candidate.model_id} not found"
                    )
            route = session.scalar(select(Route).where(Route.task == task))
            if route is None:
                route = Route(id=route_id, task=task, position=0, active=command.active)
                session.add(route)
                session.flush()
            else:
                route_id = route.id
                route.active = command.active
                old_ids = list(
                    session.scalars(
                        select(RouteCandidate.id).where(
                            RouteCandidate.route_id == route.id
                        )
                    )
                )
                if old_ids:
                    session.execute(
                        delete(CandidateHealth).where(
                            CandidateHealth.candidate_id.in_(old_ids)
                        )
                    )
                session.execute(
                    delete(RouteCandidate).where(RouteCandidate.route_id == route.id)
                )
            values = []
            for position, candidate in enumerate(command.candidates):
                candidate_id = f"candidate:{route.id}:{position}"
                session.add(
                    RouteCandidate(
                        id=candidate_id,
                        route_id=route.id,
                        model_id=candidate.model_id,
                        position=position,
                        weight=candidate.weight,
                    )
                )
                values.append(
                    {
                        "id": candidate_id,
                        "model_id": candidate.model_id,
                        "position": position,
                        "weight": candidate.weight,
                    }
                )
        return {
            "id": route_id,
            "task": task,
            "active": command.active,
            "candidates": values,
        }

    @router.post("/health/candidates/{candidate_id}/reset", status_code=204)
    def reset_candidate_health(candidate_id: str) -> Response:
        with Session(engine) as session, session.begin():
            if session.get(RouteCandidate, candidate_id) is None:
                raise HTTPException(status_code=404, detail="candidate not found")
            session.execute(
                delete(CandidateHealth).where(
                    CandidateHealth.candidate_id == candidate_id
                )
            )
        return Response(status_code=204)

    @router.post("/health/credentials/{credential_id}/reset", status_code=204)
    def reset_credential_health(credential_id: str) -> Response:
        with Session(engine) as session, session.begin():
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
        return Response(status_code=204)

    @router.get("/providers")
    def providers() -> dict[str, object]:
        with Session(engine) as session:
            provider_rows = session.scalars(
                select(Provider).order_by(Provider.id)
            ).all()
            items = []
            for provider in provider_rows:
                models = session.scalars(
                    select(ProviderModel)
                    .where(ProviderModel.provider_id == provider.id)
                    .order_by(ProviderModel.model_name)
                ).all()
                credentials = session.scalars(
                    select(CredentialRef)
                    .where(CredentialRef.provider_id == provider.id)
                    .order_by(CredentialRef.id)
                ).all()
                credential_health = {
                    row.credential_id: row
                    for row in session.scalars(
                        select(CredentialHealth).where(
                            CredentialHealth.credential_id.in_(
                                [credential.id for credential in credentials]
                            )
                        )
                    )
                }
                items.append(
                    {
                        "id": provider.id,
                        "kind": provider.kind,
                        "base_url": provider.base_url,
                        "active": provider.active,
                        "verified_at": provider.verified_at,
                        "models": [
                            {
                                "id": model.id,
                                "name": model.model_name,
                                "context_window": model.context_window,
                                "output_limit": model.output_limit,
                                "supports_tools": model.supports_tools,
                                "supports_structured": model.supports_structured,
                                "supports_text": model.supports_text,
                                "active": model.active,
                                "verified_at": model.verified_at,
                            }
                            for model in models
                        ],
                        "credentials": [
                            {
                                "credential_id": credential.id,
                                "label": credential.label,
                                "weight": credential.weight,
                                "mask": "********",
                                "health": {
                                    "disabled": (
                                        credential_health.get(credential.id).disabled
                                        if credential.id in credential_health
                                        else False
                                    ),
                                    "failure_count": (
                                        credential_health.get(
                                            credential.id
                                        ).failure_count
                                        if credential.id in credential_health
                                        else 0
                                    ),
                                    "last_error_class": (
                                        credential_health.get(
                                            credential.id
                                        ).last_error_class
                                        if credential.id in credential_health
                                        else None
                                    ),
                                    "cooldown_until": (
                                        credential_health.get(
                                            credential.id
                                        ).cooldown_until
                                        if credential.id in credential_health
                                        else None
                                    ),
                                },
                            }
                            for credential in credentials
                        ],
                    }
                )
            routes = session.execute(
                select(RouteCandidate, Route)
                .join(Route)
                .order_by(Route.task, Route.position, RouteCandidate.position)
            ).all()
            candidate_health = {
                row.candidate_id: row
                for row in session.scalars(select(CandidateHealth))
            }
        return {
            "model_discovery": "MANUAL_ONLY",
            "items": items,
            "routes": [
                {
                    "route_id": route.id,
                    "task": route.task,
                    "candidate_id": candidate.id,
                    "model_id": candidate.model_id,
                    "position": candidate.position,
                    "weight": candidate.weight,
                    "health": {
                        "failure_count": (
                            candidate_health.get(candidate.id).failure_count
                            if candidate.id in candidate_health
                            else 0
                        ),
                        "last_error_class": (
                            candidate_health.get(candidate.id).last_error_class
                            if candidate.id in candidate_health
                            else None
                        ),
                        "cooldown_until": (
                            candidate_health.get(candidate.id).cooldown_until
                            if candidate.id in candidate_health
                            else None
                        ),
                    },
                }
                for candidate, route in routes
            ],
        }

    @router.post("/providers/{provider_id}/credentials", status_code=201)
    def add_credential(
        provider_id: str, command: CredentialCreate
    ) -> dict[str, object]:
        if credential_service is None:
            raise HTTPException(
                status_code=503, detail="credential store is not configured"
            )
        with Session(engine) as session:
            if session.get(Provider, provider_id) is None:
                raise HTTPException(status_code=404, detail="provider not found")
        metadata = credential_service.add(
            provider_id, command.label, command.secret, weight=command.weight
        )
        return metadata.model_dump(exclude={"opaque_ref"})

    @router.delete(
        "/providers/{provider_id}/credentials/{credential_id}", status_code=204
    )
    def delete_credential(provider_id: str, credential_id: str) -> Response:
        if credential_service is None:
            raise HTTPException(
                status_code=503, detail="credential store is not configured"
            )
        with Session(engine) as session:
            row = session.get(CredentialRef, credential_id)
            if row is None or row.provider_id != provider_id:
                raise HTTPException(status_code=404, detail="credential not found")
        credential_service.delete(credential_id)
        return Response(status_code=204)

    @router.post("/research-runs", status_code=202)
    def create_research_run(
        command: CreateResearchRun,
        response: Response,
        idempotency_key: str = Header(alias="Idempotency-Key", min_length=1),
    ) -> dict[str, object]:
        try:
            projection = kernel.create(command, idempotency_key)
        except IdempotencyConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        response.headers["Location"] = f"/api/v2/runs/{projection.id}"
        return projection.model_dump(mode="json")

    @router.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        try:
            return kernel.get(run_id).model_dump(mode="json")
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run not found") from error

    @router.get("/runs")
    def list_runs(
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, object]:
        with Session(engine) as session:
            statement = select(Run)
            if cursor:
                statement = statement.where(Run.id > cursor)
            rows = session.scalars(statement.order_by(Run.id).limit(limit + 1)).all()
        return {
            "items": [
                {
                    "id": row.id,
                    "status": row.status,
                    "outcome": row.outcome,
                    "objective": row.objective,
                }
                for row in rows[:limit]
            ],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
        }

    @router.get("/canon")
    def accepted_canon(
        world_id: str,
        continuity: str | None = None,
        era_or_timepoint: str | None = None,
        branch_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "items": queries.accepted_graph(
                world_id,
                continuity=continuity,
                era_or_timepoint=era_or_timepoint,
                branch_id=branch_id,
            )
        }

    @router.get("/evidence/{node_id}")
    def evidence(node_id: str, branch_id: str | None = None) -> dict[str, object]:
        return {"items": queries.provenance(node_id, branch_id=branch_id)}

    @router.get("/evidence")
    def evidence_fragments(
        world_id: str,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, object]:
        with Session(engine) as session:
            statement = select(EvidenceFragment).where(
                EvidenceFragment.world_id == world_id
            )
            if cursor:
                statement = statement.where(EvidenceFragment.id > cursor)
            rows = session.scalars(
                statement.order_by(EvidenceFragment.id).limit(limit + 1)
            ).all()
        return {
            "items": [
                {
                    "id": row.id,
                    "source_revision_id": row.source_revision_id,
                    "locator": row.locator,
                    "exact_excerpt": row.exact_excerpt,
                    "domain": row.domain,
                    "support_role": row.support_role,
                }
                for row in rows[:limit]
            ],
            "next_cursor": rows[limit - 1].id if len(rows) > limit else None,
        }

    @router.get("/provenance/{node_id}")
    def provenance(node_id: str, branch_id: str | None = None) -> dict[str, object]:
        return {"items": queries.provenance(node_id, branch_id=branch_id)}

    @router.get("/relationships")
    def relationships(
        world_id: str,
        continuity: str | None = None,
        era_or_timepoint: str | None = None,
        branch_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "items": queries.relationships(
                world_id,
                continuity=continuity,
                era_or_timepoint=era_or_timepoint,
                branch_id=branch_id,
            )
        }

    @router.get("/research/{workspace_or_run_id}/gaps-conflicts")
    def gaps_conflicts(workspace_or_run_id: str) -> dict[str, object]:
        return queries.gaps_conflicts(workspace_or_run_id)

    @router.get("/coverage")
    def coverage(world_id: str, continuity: str) -> dict[str, object]:
        return {"items": queries.coverage(world_id, continuity)}

    @router.get("/runs/{run_id}/summary")
    def summary(run_id: str) -> dict[str, object]:
        value = queries.summary(run_id)
        if value is None:
            raise HTTPException(status_code=404, detail="summary not found")
        return value

    @router.get("/runs/{run_id}/flow")
    def flow(run_id: str) -> dict[str, object]:
        try:
            projection = kernel.get(run_id)
            events = kernel.events(run_id)
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        return {
            "steps": [step.model_dump(mode="json") for step in projection.steps],
            "events": [event.model_dump(mode="json") for event in events],
        }

    @router.get("/runs/{run_id}/events")
    def get_run_events(run_id: str) -> dict[str, object]:
        try:
            events = kernel.events(run_id)
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        return {
            "items": [event.model_dump(mode="json") for event in events],
            "next_cursor": None,
        }

    @router.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, object]:
        try:
            value = kernel.request_cancel(run_id, datetime.now(timezone.utc))
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except IllegalTransitionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return value.model_dump(mode="json")

    @router.post("/runs/{run_id}/resume")
    def resume_run(run_id: str) -> dict[str, object]:
        try:
            return kernel.resume(run_id).model_dump(mode="json")
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except IllegalTransitionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.post("/runs/{run_id}/retry")
    def retry_run(run_id: str) -> dict[str, object]:
        try:
            value = kernel.retry(run_id, datetime.now(timezone.utc))
            return value.model_dump(mode="json")
        except RunNotFoundError as error:
            raise HTTPException(status_code=404, detail="run not found") from error
        except IllegalTransitionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router
