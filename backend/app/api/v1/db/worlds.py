from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.dependencies import get_main_session
from app.db.schema import Universe
from app.services.universe_service import UniverseService


class AddWorldPayload(BaseModel):
    world_name: str
    franchise: str | None = None
    category: str | None = None
    continuity: str | None = None
    era: str | None = None
    parent_id: int | None = None
    auto_research: bool = True

router = APIRouter(tags=["worlds"])

@router.get("/", response_model=list[dict[str, Any]])
def list_universes_json(
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    universes = service.get_all_universes(limit=limit, offset=offset)
    return [
        {
            "id": u.id,
            "uuid": u.uuid,
            "name": u.name,
            "slug": u.slug,
            "franchise": getattr(u, 'franchise', None),
            "category": getattr(u, 'category', None),
            "summary": u.summary,
            "is_explored": u.is_explored,
        }
        for u in universes
    ]

@router.post("/", response_model=dict[str, Any])
def create_universe(
    payload: AddWorldPayload,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    existing = service.get_universe(payload.world_name)
    if existing:
        return {"status": "exists", "world_name": payload.world_name, "id": existing.id}

    universe = service.create_universe(
        name=payload.world_name,
        franchise=payload.franchise,
        category=payload.category,
        continuity=payload.continuity,
        era=payload.era,
        parent_id=payload.parent_id,
    )

    if payload.auto_research:
        import uuid

        from app.api.routers.runs import run_pipeline_in_background
        run_id = str(uuid.uuid4())
        background_tasks.add_task(run_pipeline_in_background, run_id, [universe.uuid])
        return {"status": "queued", "run_id": run_id, "world_name": universe.name}

    return {"status": "created", "world_name": universe.name, "id": universe.id}

@router.get("/by-uuid/{uuid}", response_model=Universe)
def get_universe_by_uuid(
    uuid: str,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    world = service.get_universe_by_uuid(uuid)
    if not world:
        raise HTTPException(status_code=404, detail="Universe not found")
    return world

@router.get("/{id}", response_model=Universe)
def get_universe(
    id: int | str,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    # Try by ID
    if isinstance(id, int) or str(id).isdigit():
        world = service.get_universe_by_id(int(id))
        if world: return world

    # Try by slug
    world = service.get_universe_by_slug(str(id))
    if world: return world

    raise HTTPException(status_code=404, detail="Universe not found")

@router.put("/{id}", response_model=Universe)
def update_universe(
    id: int | str,
    data: dict[str, Any],
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    return service.update_universe(id, data)

@router.delete("/{id}")
def delete_universe(
    id: int | str,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    service.delete_universe(id)
    return {"success": True}


@router.post("/{world_id}/reset-explored")
def reset_world_explored(
    world_id: int,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    if not service.reset_explored(world_id):
        raise HTTPException(status_code=404, detail="Universe not found")
    return {"status": "success"}


@router.post("/reset-all-explored")
def reset_all_explored(session: Session = Depends(get_main_session)):
    service = UniverseService(session)
    count = service.reset_all_explored()
    return {"status": "success", "count": count}


@router.post("/clear-logs")
def clear_logs():
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    exec_service.clear_logs()
    return {"status": "success"}


@router.post("/reset-database")
def reset_database():

    from app.db.extrapolation_schema import Theory
    from app.db.extrapolation_session import engine as extrapolation_engine
    from app.db.notebook_schema import NotebookEntry, NotebookUniverse
    from app.db.notebook_session import notebook_engine
    from app.db.schema import (
        Anomaly,
        Artifact,
        ArtifactRelation,
        ExecutionState,
        ModelConfig,
        TierSystem,
        WorldTier,
    )
    from app.db.session import engine as main_engine

    with Session(main_engine) as s:
        for table in [ExecutionState, ArtifactRelation, Artifact, WorldTier, TierSystem, Anomaly, ModelConfig]:
            s.exec(table.__table__.delete())
        with Session(extrapolation_engine) as extra_s:
            extra_s.exec(Theory.__table__.delete())
            extra_s.commit()
        universes = s.exec(select(Universe)).all()
        for world in universes:
            world.summary = None
            world.is_explored = False
            s.add(world)
        s.commit()

    with Session(notebook_engine) as ns:
        for table in [NotebookEntry, NotebookUniverse]:
            ns.exec(table.__table__.delete())
        ns.commit()

    return {"status": "success"}
