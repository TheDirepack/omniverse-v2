from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.services.universe_service import UniverseService
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import ExecutionState, Trait, WorldTier, TierSystem, Anomaly, ModelConfig, Universe
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
    worlds = service.repo.get_all()
    return [{"id": w.id, "name": w.name, "summary": w.summary, "is_explored": w.is_explored} for w in worlds]

@router.post("/{world_id}/reset-explored")
def reset_world_explored(world_id: int):
    service = UniverseService()
    service.reset_explored(world_id)
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
        for table in [ExecutionState, Trait, WorldTier, TierSystem, Anomaly, ModelConfig]:
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
                for name in json.load(f):
                    exists = session.exec(select(Universe).where(Universe.name == name)).first()
                    if not exists:
                        session.add(Universe(name=name, summary=None, is_explored=False))
        session.commit()
    
    with Session(unconfirmed_engine) as session:
        for table in [UnconfirmedUniverse, UnconfirmedTrait]:
            session.exec(table.__table__.delete())
        session.commit()

    return {"status": "success"}

@router.post("/clear-logs")
def clear_logs():
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    exec_service.clear_logs()
    return {"status": "success"}
