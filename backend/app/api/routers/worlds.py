from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.services.universe_service import UniverseService
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import (
    ExecutionState, Trait, WorldTier, TierSystem, Anomaly, ModelConfig, Universe,
    Entity, EntityAlias, Claim, InferenceRule, InferredClaim,
)
from app.db.unconfirmed_session import engine as unconfirmed_engine
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait
from app.db.extrapolation_session import engine as extrapolation_engine
from app.db.extrapolation_schema import Theory
from pathlib import Path
import json

router = APIRouter(prefix="/worlds", tags=["worlds"])

class AddWorldPayload(BaseModel):
    world_name: str
    auto_research: bool = True

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
        background_tasks.add_task(run_pipeline_in_background, run_id, [payload.world_name])
        return {"status": "queued", "run_id": run_id, "world_name": payload.world_name}
    return {"status": "created", "world_name": payload.world_name}

@router.get("/")
def get_worlds():
    service = UniverseService()
    worlds = service.get_all_universes()
    return [
        {
            "id": w.id,
            "slug": w.slug,
            "name": w.name,
            "franchise": w.franchise,
            "category": w.category,
            "continuity": w.continuity,
            "era": w.era,
            "summary": w.summary,
            "is_explored": w.is_explored
        }
        for w in worlds
    ]

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
    unexplored = [u.name for u in service.repo.get_all() if not u.is_explored]
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
def reset_database():
    with Session(engine) as session:
        # Deletion order matters: PRAGMA foreign_keys=ON is enabled on this
        # engine (see db/session.py), so any table must be deleted AFTER
        # every table that references it via a foreign key, or SQLite raises
        # an IntegrityError. InferredClaim references Entity/Claim/
        # InferenceRule; Claim and EntityAlias reference Entity -- so those
        # go first, then Entity, then the independent InferenceRule.
        # WorldTier references TierSystem, so it must precede it too
        # (already correct below).
        for table in [
            ExecutionState,
            InferredClaim, Claim, EntityAlias, Entity, InferenceRule,
            Trait, WorldTier, TierSystem, Anomaly, ModelConfig,
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
                    exists = session.exec(select(Universe).where(Universe.slug == slug)).first()
                    if not exists:
                        session.add(Universe(
                            slug=slug,
                            name=w_data.get("name"),
                            franchise=w_data.get("franchise"),
                            category=w_data.get("category"),
                            continuity=w_data.get("continuity"),
                            era=w_data.get("era"),
                            summary=None,
                            is_explored=False
                        ))
        session.commit()
    
    with Session(unconfirmed_engine) as session:
        # Same FK-ordering issue as above: unconfirmed.db also enables
        # PRAGMA foreign_keys=ON (unconfirmed_session.py), and
        # UnconfirmedTrait.universe_id references unconfirmed_universe.id.
        # Deleting UnconfirmedUniverse before UnconfirmedTrait raises an
        # IntegrityError the moment any trait rows exist -- this was the
        # actual cause of "reset has issues with Unconfirmed.db". Child
        # table must be deleted first.
        for table in [UnconfirmedTrait, UnconfirmedUniverse]:
            session.exec(table.__table__.delete())
        session.commit()

    return {"status": "success"}

@router.post("/clear-logs")
def clear_logs():
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    exec_service.clear_logs()
    return {"status": "success"}
