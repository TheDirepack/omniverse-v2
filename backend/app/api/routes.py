import json
import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from app.db.session import engine
from app.db.schema import Universe, TierSystem, WorldTier, Anomaly, Theory, ExecutionState, Setting, ProviderConfig, ProviderKey, AgentRouteFallback, Trait, ModelConfig
from app.agents.workflow import app_graph
from app.agents.nodes import research_single_world
from app.core.state import ACTIVE_RUNS, ABORTED_RUNS

router = APIRouter()

class SetupModelRoute(BaseModel):
    task_type: str
    model_name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None

class SetupSetting(BaseModel):
    key: str
    value: Optional[str] = None


class ProviderPayload(BaseModel):
    id: Optional[int] = None
    name: str
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[str] = None

class ProviderKeyPayload(BaseModel):
    id: Optional[int] = None
    provider_id: int
    api_key: str
    priority: int = 0

class AgentRouteFallbackPayload(BaseModel):
    id: Optional[int] = None
    task_type: str = Field(min_length=1)
    priority: int = 0
    provider_id: Optional[int] = None
    model_name: Optional[str] = None



class AddWorldPayload(BaseModel):
    world_name: str
    auto_research: bool = True


class FocusedSearchPayload(BaseModel):
    world_name: str
    feature: str


class OrchestratePayload(BaseModel):
    worlds: List[str]


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/settings")
def get_settings():
    with Session(engine) as session:
        settings = session.exec(select(Setting)).all()
        providers = session.exec(select(ProviderConfig)).all()
        routes = session.exec(select(AgentRouteFallback).order_by(AgentRouteFallback.priority)).all()
        
        provider_details = []
        for p in providers:
            keys = session.exec(select(ProviderKey).where(ProviderKey.provider_id == p.id).order_by(ProviderKey.priority)).all()
            provider_details.append({
                "id": p.id,
                "name": p.name,
                "provider_type": p.provider_type,
                "base_url": p.base_url,
                "models": p.models,
                "keys": [{"id": k.id, "api_key": k.api_key, "priority": k.priority} for k in keys]
            })

        return {
            "general_settings": {s.key: s.value for s in settings},
            "providers": provider_details,
            "agent_routes": [
                {
                    "id": r.id,
                    "task_type": r.task_type,
                    "provider_id": r.provider_id,
                    "model_name": r.model_name,
                    "priority": r.priority,
                } for r in routes
            ],
        }


@router.post("/settings/general")
def update_general_setting(payload: SetupSetting):
    with Session(engine) as session:
        setting = session.get(Setting, payload.key)
        if not setting:
            setting = Setting(key=payload.key, value=None)
        setting.value = payload.value
        session.add(setting)
        session.commit()
    return {"status": "success", "message": f"Setting '{payload.key}' updated successfully."}


@router.post("/providers")
def upsert_provider(payload: ProviderPayload):
    with Session(engine) as session:
        provider = session.get(ProviderConfig, payload.id) if payload.id else session.exec(select(ProviderConfig).where(ProviderConfig.name == payload.name)).first()
        if not provider:
            provider = ProviderConfig(name=payload.name)
        provider.name = payload.name
        provider.provider_type = payload.provider_type
        provider.base_url = payload.base_url
        provider.models = payload.models
        session.add(provider)
        session.commit()
        session.refresh(provider)
        return {"status": "success", "provider": {"id": provider.id, "name": provider.name}}

@router.post("/providers/keys")
def upsert_provider_key(payload: ProviderKeyPayload):
    with Session(engine) as session:
        key = session.get(ProviderKey, payload.id) if payload.id else None
        if not key:
            key = ProviderKey(provider_id=payload.provider_id)
        key.api_key = payload.api_key
        key.priority = payload.priority
        session.add(key)
        session.commit()
        session.refresh(key)
        return {"status": "success", "key_id": key.id}

@router.delete("/providers/keys/{key_id}")
def delete_provider_key(key_id: int):
    with Session(engine) as session:
        key = session.get(ProviderKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="Key not found")
        session.delete(key)
        session.commit()
        return {"status": "success"}

@router.get("/providers")
def get_providers():
    with Session(engine) as session:
        providers = session.exec(select(ProviderConfig)).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "provider_type": p.provider_type,
                "base_url": p.base_url,
                "models": p.models,
                "keys": [
                    {"id": k.id, "api_key": k.api_key, "priority": k.priority}
                    for k in session.exec(select(ProviderKey).where(ProviderKey.provider_id == p.id).order_by(ProviderKey.priority)).all()
                ]
            }
            for p in providers
        ]



@router.get("/providers/{provider_id}/models")
def get_provider_models(provider_id: int):
    from app.core.router import router as model_router
    return {"models": model_router.list_provider_models(provider_id)}


@router.post("/agent-routes")
def upsert_agent_route(payload: AgentRouteFallbackPayload):
    with Session(engine) as session:
        if payload.provider_id is not None:
            provider = session.get(ProviderConfig, payload.provider_id)
            if not provider:
                raise HTTPException(status_code=422, detail=f"Provider with id {payload.provider_id} not found")
        
        route = None
        if payload.id:
            route = session.get(AgentRouteFallback, payload.id)
            
        if not route:
            route = AgentRouteFallback(task_type=payload.task_type)
            
        route.provider_id = payload.provider_id
        route.model_name = payload.model_name
        route.priority = payload.priority
        session.add(route)
        session.commit()
    return {"status": "success"}

@router.delete("/agent-routes/{route_id}")
def delete_agent_route(route_id: int):
    with Session(engine) as session:
        route = session.get(AgentRouteFallback, route_id)
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")
        session.delete(route)
        session.commit()
        return {"status": "success"}

@router.get("/agent-routes")
def get_agent_routes():
    with Session(engine) as session:
        routes = session.exec(select(AgentRouteFallback).order_by(AgentRouteFallback.priority)).all()
        return [
            {
                "id": r.id,
                "task_type": r.task_type,
                "provider_id": r.provider_id,
                "model_name": r.model_name,
                "priority": r.priority,
            }
            for r in routes
        ]



@router.post("/worlds")
def add_world(payload: AddWorldPayload, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        world = session.exec(select(Universe).where(Universe.name == payload.world_name)).first()
        if not world:
            world = Universe(name=payload.world_name, summary=None)
            session.add(world)
            session.commit()
    if payload.auto_research:
        run_id = str(uuid.uuid4())
        background_tasks.add_task(run_pipeline_in_background, run_id, [payload.world_name])
        return {"status": "queued", "run_id": run_id, "world_name": payload.world_name}
    return {"status": "created", "world_name": payload.world_name}


@router.get("/worlds")
def get_worlds():
    with Session(engine) as session:
        worlds = session.exec(select(Universe).order_by(Universe.name)).all()
        return [{"id": w.id, "name": w.name, "summary": w.summary, "is_explored": w.is_explored} for w in worlds]


@router.post("/worlds/{world_id}/clear-explored")
def clear_world_explored(world_id: int):
    with Session(engine) as session:
        world = session.get(Universe, world_id)
        if not world:
            raise HTTPException(status_code=404, detail="World not found")
        world.is_explored = False
        session.add(world)
        session.commit()
    return {"status": "success"}


@router.post("/worlds/clear-explored")
def clear_all_explored():
    with Session(engine) as session:
        worlds = session.exec(select(Universe)).all()
        for world in worlds:
            world.is_explored = False
            session.add(world)
        session.commit()
    return {"status": "success", "count": len(worlds)}


@router.post("/worlds/research-unexplored")
def research_unexplored(background_tasks: BackgroundTasks):
    with Session(engine) as session:
        worlds = session.exec(select(Universe).where(Universe.is_explored == False)).all()  # noqa: E712
        names = [world.name for world in worlds]
    if not names:
        return {"status": "noop", "run_id": None, "worlds": []}
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline_in_background, run_id, names)
    return {"status": "started", "run_id": run_id, "worlds": names}


@router.post("/focused-search")
def focused_search(payload: FocusedSearchPayload, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_focused_search_in_background, run_id, payload.world_name, payload.feature)
    return {"status": "started", "run_id": run_id, "world_name": payload.world_name, "feature": payload.feature}


@router.post("/reset-database")
def reset_database():
    with Session(engine) as session:
        for table in [ExecutionState, Trait, WorldTier, TierSystem, Theory, Anomaly, ModelConfig]:
            session.exec(table.__table__.delete())
        worlds = session.exec(select(Universe)).all()
        for world in worlds:
            world.summary = None
            world.is_explored = False
            session.add(world)
        json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
        if json_path.exists():
            with open(json_path) as f:
                for name in json.load(f):
                    exists = session.exec(select(Universe).where(Universe.name == name)).first()
                    if not exists:
                        session.add(Universe(name=name, summary=None, is_explored=False))
        session.commit()
    return {"status": "success"}


@router.post("/clear-logs")
def clear_logs():
    with Session(engine) as session:
        session.exec(ExecutionState.__table__.delete())
        session.commit()
    return {"status": "success"}


async def run_pipeline_in_background(run_id: str, target_worlds: List[str]):
    from app.core.agent_engine import run_fetch_cache
    if run_id in ABORTED_RUNS:
        return
    run_fetch_cache.clear()
    ACTIVE_RUNS.add(run_id)
    # Initialize the workflow state
    inputs = {
        "target_worlds": target_worlds,
        "research_results": [],
        "verified_worlds": [],
        "current_tier_system": None,
        "system_stable": False,
        "anomalies": [],
        "generated_theories": [],
        "run_id": run_id,
        "active_task": "RESEARCH",
        "errors": []
    }
    try:
        # Run compiled LangGraph state machine
        await app_graph.ainvoke(inputs)
    except Exception as e:
        print(f"[API] Error executing pipeline: {e}")
        # Log critical failure
        with Session(engine) as session:
            err_log = ExecutionState(
                run_id=run_id,
                node_name="Manager",
                thought=f"Critical Execution Failure: {str(e)}",
                status="FAILED",
                state_snapshot=json.dumps({"error": str(e)})
            )
            session.add(err_log)
            session.commit()
    finally:
        ACTIVE_RUNS.discard(run_id)


async def run_focused_search_in_background(run_id: str, world_name: str, feature: str):
    ACTIVE_RUNS.add(run_id)
    try:
        if run_id in ABORTED_RUNS:
            raise RuntimeError("Run aborted before start")
        await research_single_world(world_name, run_id, focus=feature)
        with Session(engine) as session:
            session.add(ExecutionState(run_id=run_id, node_name="Focused Search", thought="Focused search completed", status="COMPLETED", state_snapshot=json.dumps({"world_name": world_name, "feature": feature})))
            session.commit()
    except Exception as e:
        with Session(engine) as session:
            session.add(ExecutionState(run_id=run_id, node_name="Focused Search", thought=f"Focused search failed: {e}", status="FAILED", state_snapshot=json.dumps({"error": str(e)})))
            session.commit()
    finally:
        ACTIVE_RUNS.discard(run_id)


@router.post("/orchestrate")
def trigger_orchestration(payload: OrchestratePayload, background_tasks: BackgroundTasks):
    if not payload.worlds:
        raise HTTPException(status_code=400, detail="Must provide at least one target world name.")
        
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline_in_background, run_id, payload.worlds)
    return {"status": "started", "run_id": run_id, "worlds": payload.worlds}


@router.get("/results")
def get_results():
    with Session(engine) as session:
        universes = session.exec(select(Universe)).all()
        tiers_system = session.exec(select(TierSystem).order_by(TierSystem.created_at.desc())).first()
        
        universe_ids = [u.id for u in universes]
        
        # Bulk fetch tiers and theories to avoid N+1
        tiers_map = {}
        if universe_ids:
            tiers = session.exec(select(WorldTier).where(WorldTier.universe_id.in_(universe_ids))).all()
            for t in tiers:
                tiers_map[t.universe_id] = t
                
        theories_map = {}
        if universe_ids:
            theories = session.exec(select(Theory).where(Theory.universe_id.in_(universe_ids))).all()
            for th in theories:
                theories_map[th.universe_id] = th
        
        results = []
        for uni in universes:
            wt = tiers_map.get(uni.id)
            th = theories_map.get(uni.id)
            
            results.append({
                "id": uni.id,
                "name": uni.name,
                "summary": uni.summary,
                "is_explored": uni.is_explored,
                "tier": wt.tier_number if wt else None,
                "tier_justification": wt.justification if wt else None,
                "theory": th.theory_text if th else None,
                "theory_audit": th.auditor_feedback if th else None
            })
            
        anomalies = session.exec(select(Anomaly).order_by(Anomaly.detected_at.desc())).all()
        
        return {
            "tier_system": tiers_system.system_definition if tiers_system else None,
            "worlds": results,
            "anomalies": [{"world_id": a.universe_id, "description": a.description, "detected_at": str(a.detected_at)} for a in anomalies]
        }


@router.get("/tiers")
def get_tiers():
    return get_results()


@router.get("/theories")
def get_theories():
    with Session(engine) as session:
        theories = session.exec(select(Theory).order_by(Theory.created_at.desc())).all()
        return [{"id": t.id, "universe_id": t.universe_id, "theory": t.theory_text, "auditor_feedback": t.auditor_feedback, "created_at": str(t.created_at)} for t in theories]


@router.get("/model-status")
def model_status():
    with Session(engine) as session:
        routes = session.exec(select(AgentRoute)).all()
        providers = {p.id: p for p in session.exec(select(ProviderConfig)).all()}
        route_status = []
        for route in routes:
            provider = providers.get(route.provider_id)
            route_status.append({
                "task_type": route.task_type,
                "configured": bool(provider and provider.provider_type and route.model_name),
                "provider": provider.name if provider else None,
                "model": route.model_name,
            })
        return {"initialized": True, "routes": route_status}


@router.get("/agent-activity")
def agent_activity():
    with Session(engine) as session:
        logs = session.exec(select(ExecutionState).order_by(ExecutionState.created_at.desc()).limit(50)).all()
        return {"active_runs": list(ACTIVE_RUNS), "logs": [{"run_id": l.run_id, "node_name": l.node_name, "thought": l.thought, "status": l.status, "created_at": str(l.created_at)} for l in logs]}


@router.post("/reset-activity")
def reset_activity():
    return clear_logs()


@router.post("/abort")
def abort_run(payload: dict):
    run_id = payload.get("runId") or payload.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="runId required")
    ABORTED_RUNS.add(run_id)
    with Session(engine) as session:
        session.add(ExecutionState(run_id=run_id, node_name="Manager", thought="Abort requested", status="ABORT_REQUESTED", state_snapshot="{}"))
        session.commit()
    return {"status": "abort_requested", "run_id": run_id}


@router.get("/logs/{run_id}")
async def get_realtime_logs(run_id: str):
    async def log_generator():
        last_id = 0
        while True:
            # Fetch any new logs
            with Session(engine) as session:
                statement = select(ExecutionState).where(
                    ExecutionState.run_id == run_id,
                    ExecutionState.id > last_id
                ).order_by(ExecutionState.id)
                new_logs = session.exec(statement).all()
                for log in new_logs:
                    yield f"data: {json.dumps({'node_name': log.node_name, 'thought': log.thought, 'status': log.status, 'created_at': str(log.created_at)})}\n\n"
                    last_id = log.id
                    if log.status == "FAILED":
                        yield "data: {\"finished\": true, \"failed\": true}\n\n"
                        return
                    if log.status == "COMPLETED" and log.node_name in {"Ontological Theorist", "Focused Search"}:
                        yield "data: {\"finished\": true}\n\n"
                        return
            await asyncio.sleep(1)

    return StreamingResponse(log_generator(), media_type="text/event-stream")
