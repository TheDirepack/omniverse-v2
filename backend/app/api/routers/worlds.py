import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.dependencies import get_main_session
from app.db.extrapolation_schema import Theory
from app.db.extrapolation_session import engine as extrapolation_engine
from app.db.schema import (
    Anomaly,
    Artifact,
    ArtifactRelation,
    ExecutionState,
    ModelConfig,
    TierSystem,
    Universe,
    WorldTier,
)
from app.db.session import engine
from app.db.notebook_schema import NotebookEntry, NotebookUniverse
from app.db.notebook_session import notebook_engine
from app.services.universe_service import UniverseService

router = APIRouter(prefix="/worlds", tags=["worlds"])


class AddWorldPayload(BaseModel):
    world_name: str
    parent_id: int | None = None
    auto_research: bool = True


class ImportWorldPayload(BaseModel):
    world_id: str
    auto_research: bool = True


class SnapshotPayload(BaseModel):
    name: str
    snapshot_type: str = "FULL"

class SnapshotResponse(BaseModel):
    id: int
    name: str
    created_at: str
    snapshot_type: str


class UniverseResponse(BaseModel):
    id: int
    uuid: str
    slug: str
    name: str
    summary: str | None = None
    is_explored: bool


@router.post("/snapshots")
def create_snapshot(payload: SnapshotPayload):
    from app.db.notebook_schema import Snapshot
    with Session(notebook_engine) as session:
        # In a real implementation, we would backup the DB files here
        # For now, we record the snapshot metadata
        snapshot = Snapshot(
            name=payload.name,
            snapshot_type=payload.snapshot_type,
            metadata="Database state captured."
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        return SnapshotResponse(
            id=snapshot.id,
            name=snapshot.name,
            created_at=str(snapshot.created_at),
            snapshot_type=snapshot.snapshot_type
        )

@router.get("/snapshots")
def list_snapshots():
    from app.db.notebook_schema import Snapshot
    with Session(notebook_engine) as session:
        snapshots = session.exec(select(Snapshot)).all()
        return [
            SnapshotResponse(
                id=s.id,
                name=s.name,
                created_at=str(s.created_at),
                snapshot_type=s.snapshot_type
            )
            for s in snapshots
        ]

@router.delete("/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: int):
    from app.db.notebook_schema import Snapshot
    with Session(notebook_engine) as session:
        snapshot = session.get(Snapshot, snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        session.delete(snapshot)
        session.commit()
        return {"status": "success"}
@router.post("/import")
def import_world(payload: ImportWorldPayload, background_tasks: BackgroundTasks):
    service = UniverseService()
    world = service.import_from_registry(payload.world_id)
    if not world:
        return {
            "status": "error",
            "message": f"World '{payload.world_id}' not found in registry.",
        }

    if payload.auto_research and world.name:
        import uuid

        run_id = str(uuid.uuid4())
        from app.api.routers.runs import run_pipeline_in_background

        background_tasks.add_task(
            run_pipeline_in_background, run_id, [world.uuid]
        )
        return {
            "status": "queued",
            "run_id": run_id,
            "world_id": payload.world_id,
            "world_name": world.name,
        }
    return {
        "status": "imported",
        "world_id": payload.world_id,
        "world_name": world.name,
    }


@router.post("/create")
def create_world(payload: AddWorldPayload, background_tasks: BackgroundTasks):
    service = UniverseService()
    existing = service.get_universe(payload.world_name)
    if existing:
        return {"status": "exists", "world_name": payload.world_name, "id": existing.id}

    world = service.create_universe(
        name=payload.world_name,
        parent_id=payload.parent_id,
    )

    if payload.auto_research and world.name:
        import uuid

        run_id = str(uuid.uuid4())
        from app.api.routers.runs import run_pipeline_in_background

        background_tasks.add_task(
            run_pipeline_in_background, run_id, [world.uuid]
        )
        return {"status": "queued", "run_id": run_id, "world_name": world.name}
    return {"status": "created", "world_name": world.name, "id": world.id}


@router.post("/")
def add_world(payload: AddWorldPayload, background_tasks: BackgroundTasks):
    service = UniverseService()
    world = service.get_universe(payload.world_name)
    if not world:
        world = service.create_universe(payload.world_name)

    if payload.auto_research:
        import uuid

        run_id = str(uuid.uuid4())
        from app.api.routers.runs import run_pipeline_in_background

        background_tasks.add_task(
            run_pipeline_in_background, run_id, [world.uuid]
        )
        return {"status": "queued", "run_id": run_id, "world_name": payload.world_name}
    return {"status": "created", "world_name": payload.world_name}


@router.get("/")
def get_worlds(
    limit: int = 100, 
    offset: int = 0, 
    fields: list[str] | None = None,
    session: Session = Depends(get_main_session)
):
    service = UniverseService()
    worlds = service.get_all_universes(limit=limit, offset=offset)
    
    results = []
    for w in worlds:
        # Get metadata from artifacts
        artifacts = session.exec(
            select(Artifact).where(Artifact.universe_id == w.id)
        ).all()
        meta = {a.type: a.name for a in artifacts}
        
        if fields:
            # Construct a dict with requested fields
            res = {}
            for f in fields:
                if hasattr(w, f):
                    res[f] = getattr(w, f)
                elif f in meta:
                    res[f] = meta[f]
                else:
                    res[f] = None
            results.append(res)
        else:
            results.append(
                UniverseResponse(
                    id=w.id,
                    uuid=w.uuid,
                    slug=w.slug or f"universe-{w.id}",
                    name=w.name,
                    summary=w.summary,
                    is_explored=w.is_explored,
                )
            )
    return results


@router.post("/{world_id}/reset-explored")
def reset_world_explored(world_id: int):
    service = UniverseService()
    if not service.reset_explored(world_id):
        raise HTTPException(status_code=404, detail="Universe not found")
    return {"status": "success"}


@router.post("/reset-all-explored")
def reset_all_explored():
    service = UniverseService()
    count = service.reset_all_explored()
    return {"status": "success", "count": count}


@router.post("/research-unexplored")
def research_unexplored(background_tasks: BackgroundTasks):
    service = UniverseService()
    unexplored = [u.uuid for u in service.repo.get_all() if not u.is_explored]
    if not unexplored:
        return {"status": "noop", "run_id": None, "worlds": []}
    import uuid

    run_id = str(uuid.uuid4())
    from app.api.routers.runs import run_pipeline_in_background

    background_tasks.add_task(run_pipeline_in_background, run_id, unexplored)
    return {"status": "started", "run_id": run_id, "worlds": unexplored}


@router.delete("/{world_id}")
def delete_world(world_id: int):
    service = UniverseService()
    service.delete_universe(world_id)
    return {"status": "success"}


@router.post("/reset-database")
def reset_database(create_snapshot: bool = True, snapshot_name: str = "Auto-Reset-Snapshot"):
    if create_snapshot:
        from app.db.notebook_schema import Snapshot
        with Session(notebook_engine) as snap_session:
            snapshot = Snapshot(
                name=snapshot_name,
                snapshot_type="FULL",
                metadata="Automatic snapshot before reset."
            )
            snap_session.add(snapshot)
            snap_session.commit()

    with Session(engine) as session:
        # Deletion order matters: PRAGMA foreign_keys=ON is enabled on this
        # engine (see db/session.py), so any table must be deleted AFTER
        # every table that references it via a foreign key, or SQLite raises
        # an IntegrityError.
        # WorldTier references TierSystem, so it must precede it too
        # (already correct below).
        for table in [
            ExecutionState,
            ArtifactRelation,
            Artifact,
            WorldTier,
            TierSystem,
            Anomaly,
            ModelConfig,
        ]:
            session.exec(table.__table__.delete())

        with Session(extrapolation_engine) as extra_session:
            extra_session.exec(Theory.__table__.delete())

        universes = session.exec(select(Universe)).all()
        for world in universes:
            world.summary = None
            world.is_explored = False
            world.raw_data = None
            session.add(world)

        json_path = Path(__file__).parent.parent.parent / "db" / "default_worlds.json"
        if json_path.exists():
            with open(json_path) as f:
                default_worlds = json.load(f)
                for w_data in default_worlds:
                    slug = w_data.get("id")
                    exists = session.exec(
                        select(Universe).where(Universe.slug == slug)
                    ).first()
                    if not exists:
                        session.add(
                            Universe(
                                 slug=slug,
                                 name=w_data.get("name"),
                                 summary=None,
                                 is_explored=False,
                             )

                        )
        session.commit()

    with Session(notebook_engine) as session:
        # Same FK-ordering issue as above: notebook.db also enables
        # PRAGMA foreign_keys=ON (notebook_session.py), and
        # NotebookClaim.universe_id references notebook_universe.id.
        # Deleting NotebookUniverse before NotebookClaim raises an
        # IntegrityError the moment any claim rows exist -- this was the
        # actual cause of "reset has issues with Notebook.db". Child
        # table must be deleted first.
        for table in [NotebookEntry, NotebookUniverse]:
            session.exec(table.__table__.delete())
        session.commit()

    return {"status": "success"}


@router.get("/registry")
def list_registry(q: str | None = Query(default=None)):
    json_path = Path(__file__).parent.parent.parent / "db" / "default_worlds.json"
    if not json_path.exists():
        return {"worlds": []}
    with open(json_path) as f:
        entries = json.load(f)
    if q:
        q_lower = q.lower()
        entries = [
            e for e in entries
            if q_lower in e.get("name", "").lower()
            or q_lower in e.get("id", "").lower()
        ]
    return {"worlds": entries[:50]}


@router.get("/search-duplicates")
def search_duplicates(name: str = Query(...)):
    service = UniverseService()
    return {"candidates": service.find_duplicates(name)}


from pydantic import BaseModel


class MergeWorldsPayload(BaseModel):
    keep_id: int
    merge_id: int

@router.post("/merge")
def merge_worlds(payload: MergeWorldsPayload):
    service = UniverseService()
    return service.merge_worlds(payload.keep_id, payload.merge_id)


@router.get("/by-uuid/{uuid}", response_model=UniverseResponse)
def get_world_by_uuid(uuid: str):
    service = UniverseService()
    world = service.get_universe_by_uuid(uuid)
    if not world:
        raise HTTPException(status_code=404, detail="World not found")
    return {
        "id": world.id,
        "uuid": world.uuid,
        "slug": world.slug,
        "name": world.name,
        "summary": world.summary,
        "is_explored": world.is_explored,
    }


@router.post("/clear-logs")
def clear_logs():
    from app.services.execution_service import ExecutionService

    exec_service = ExecutionService()
    exec_service.clear_logs()
    return {"status": "success"}
