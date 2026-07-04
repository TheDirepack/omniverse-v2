import json
import asyncio
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from app.db.session import engine
from app.db.unconfirmed_session import engine as unconfirmed_engine
from app.db.extrapolation_session import engine as extrapolation_engine
from app.db.unconfirmed_schema import UnconfirmedUniverse, UnconfirmedTrait
from app.db.schema import Universe, TierSystem, WorldTier, Anomaly, ExecutionState, Setting, ProviderConfig, ProviderKey, AgentRouteFallback, Trait, ModelConfig, CandidateHealth
from app.db.extrapolation_schema import Theory
from app.agents.workflow import app_graph
from app.agents.nodes import research_single_world
from app.agents.agent_names import AGENT_NAMES
from app.core.state import (
    ACTIVE_RUNS, ABORTED_RUNS, add_active_run, remove_run, abort_run, is_aborted, get_active_runs
)

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
    models: Optional[str] = None



class AddWorldPayload(BaseModel):
    world_name: str
    auto_research: bool = True


class FocusedSearchPayload(BaseModel):
    worlds: List[str]
    features: List[str]


class OrchestratePayload(BaseModel):
    worlds: List[str]

class ExtrapolatePayload(BaseModel):
    scope: str = Field(..., pattern="^(all|worlds|tier)$")
    worlds: Optional[List[str]] = None
    tier: Optional[int] = None


@router.get("/traits")
def get_traits(universe_ids: Optional[str] = None):
    with Session(engine) as session:
        query = select(Trait)
        if universe_ids:
            ids = [int(id_str) for id_str in universe_ids.split(",") if id_str.strip()]
            query = query.where(Trait.universe_id.in_(ids))
        
        return session.exec(query).all()

@router.get("/traits/unconfirmed")
def get_unconfirmed_traits(universe_ids: Optional[str] = None):
    with Session(unconfirmed_engine) as session:
        # We want to return the trait and the universe name
        query = select(UnconfirmedTrait, UnconfirmedUniverse.name).join(UnconfirmedUniverse)
        if universe_ids:
            names = [n.strip() for n in universe_ids.split(",") if n.strip()]
            query = query.where(UnconfirmedUniverse.name.in_(names))
        
        results = session.exec(query).all()
        
        # Format as list of dicts including the name
        output = []
        for trait, name in results:
            trait_dict = trait.model_dump()
            trait_dict["universe_name"] = name
            output.append(trait_dict)
            
        return output


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
                "models": r.models,
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
            session.add(provider)
            session.flush()

        update_data = payload.model_dump(exclude_unset=True)
        update_data.pop("id", None)
        for key, value in update_data.items():
            setattr(provider, key, value)

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

@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: int):
    with Session(engine) as session:
        provider = session.get(ProviderConfig, provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        session.delete(provider)
        session.commit()
        return {"status": "success"}

@router.delete("/worlds/{world_id}")
def delete_world(world_id: int):
    with Session(engine) as session:
        universe = session.get(Universe, world_id)
        if not universe:
            raise HTTPException(status_code=404, detail="World not found")
        
        # Delete related data first to avoid FK constraints
        session.exec(WorldTier.__table__.delete().where(WorldTier.universe_id == world_id))
        session.exec(Trait.__table__.delete().where(Trait.universe_id == world_id))
        session.exec(Anomaly.__table__.delete().where(Anomaly.universe_id == world_id))
        
        with Session(extrapolation_engine) as extra_session:
            extra_session.exec(Theory.__table__.delete().where(Theory.universe_id == world_id))
        
        session.delete(universe)
        session.commit()
        return {"status": "success"}

@router.post("/settings/reset-health")
def reset_candidate_health():
    with Session(engine) as session:
        session.exec(select(CandidateHealth)).all() # just to make sure it exists
        # To reset all, we can just delete them or set failure_count=0
        # Deleting them is cleanest as _get_health will recreate them
        session.exec(CandidateHealth.__table__.delete())
        session.commit()
    return {"status": "success", "message": "All candidate circuit breakers reset."}

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
async def get_provider_models(provider_id: int):
    from app.core.provider_models import fetch_live_models
    from app.db.schema import ProviderConfig
    with Session(engine) as session:
        provider = session.get(ProviderConfig, provider_id)
        if not provider:
            return {"models": []}
    models = await fetch_live_models(provider)
    return {"models": models}


@router.get("/agent-names")
def get_agent_names():
    return AGENT_NAMES

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
        route.models = payload.models
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
            "models": r.models,
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


@router.post("/worlds/{world_id}/reset-explored")
def reset_world_explored(world_id: int):
    with Session(engine) as session:
        world = session.get(Universe, world_id)
        if not world:
            raise HTTPException(status_code=404, detail="World not found")
        world.is_explored = False
        session.add(world)
        session.commit()
    return {"status": "success"}


@router.post("/worlds/reset-all-explored")
def reset_all_explored():
    with Session(engine) as session:
        worlds = session.exec(select(Universe).where(Universe.is_explored == True)).all()  # noqa: E712
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
    background_tasks.add_task(run_focused_search_in_background, run_id, payload.worlds, payload.features)
    return {"status": "started", "run_id": run_id, "worlds": payload.worlds, "features": payload.features}


@router.post("/reset-database")
def reset_database():
    with Session(engine) as session:
        for table in [ExecutionState, Trait, WorldTier, TierSystem, Anomaly, ModelConfig]:
            session.exec(table.__table__.delete())
        
        with Session(extrapolation_engine) as extra_session:
            extra_session.exec(Theory.__table__.delete())
            
        worlds = session.exec(select(Universe)).all()
        for world in worlds:
            world.summary = None
            world.is_explored = False
            world.raw_data = None
            session.add(world)
        json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
        if json_path.exists():
            with open(json_path) as f:
                for name in json.load(f):
                    exists = session.exec(select(Universe).where(Universe.name == name)).first()
                    if not exists:
                        session.add(Universe(name=name, summary=None, is_explored=False))
        session.commit()
    
    # Clear unconfirmed staging database
    with Session(unconfirmed_engine) as session:
        for table in [UnconfirmedUniverse, UnconfirmedTrait]:
            session.exec(table.__table__.delete())
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
    if await is_aborted(run_id):
        with Session(engine) as session:
            session.add(ExecutionState(
                run_id=run_id,
                node_name="Manager",
                thought="Run aborted before initiation.",
                status="FAILED",
                state_snapshot="{}"
            ))
            session.commit()
        return
    
    # Ensure all target worlds are registered in the DB
    with Session(engine) as session:
        for name in target_worlds:
            exists = session.exec(select(Universe).where(Universe.name == name)).first()
            if not exists:
                session.add(Universe(name=name, summary=None, is_explored=False))
        session.commit()

    run_fetch_cache.clear()
    await add_active_run(run_id)
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
        "errors": [],
        "architecture_retries": 0
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
        await remove_run(run_id)


async def run_extrapolation_in_background(run_id: str, target_worlds: List[str]):
    from app.core.agent_engine import run_fetch_cache
    run_fetch_cache.clear()
    await add_active_run(run_id)
    
    inputs = {
        "target_worlds": target_worlds,
        "verified_worlds": target_worlds, # Treat these as already verified for extrapolation
        "run_id": run_id,
        "active_task": "EXTRAPOLATION",
        "generated_theories": [],
    }
    try:
        await app_graph.ainvoke(inputs)
    except Exception as e:
        print(f"[API] Error executing extrapolation: {e}")
        with Session(engine) as session:
            err_log = ExecutionState(
                run_id=run_id,
                node_name="Manager",
                thought=f"Critical Extrapolation Failure: {str(e)}",
                status="FAILED",
                state_snapshot=json.dumps({"error": str(e)})
            )
            session.add(err_log)
            session.commit()
    finally:
        await remove_run(run_id)


async def run_focused_search_in_background(run_id: str, target_worlds: List[str], focused_features: List[str]):
    from app.core.agent_engine import run_fetch_cache
    await add_active_run(run_id)
    try:
        if await is_aborted(run_id):
            raise RuntimeError("Run aborted before start")
        
        run_fetch_cache.clear()
        
        # Initialize the workflow state for focused search
        inputs = {
            "target_worlds": target_worlds,
            "focused_features": focused_features,
            "is_focused_search": True,
            "research_results": [],
            "verified_worlds": [],
            "current_tier_system": None,
            "system_stable": False,
            "anomalies": [],
            "generated_theories": [],
            "run_id": run_id,
            "active_task": "RESEARCH",
            "errors": [],
            "architecture_retries": 0
        }
        
        # Run compiled LangGraph state machine
        await app_graph.ainvoke(inputs)
        
    except Exception as e:
        with Session(engine) as session:
            err_log = ExecutionState(
                run_id=run_id,
                node_name="Focused Search",
                thought=f"Focused search failed: {str(e)}",
                status="FAILED",
                state_snapshot=json.dumps({"error": str(e)})
            )
            session.add(err_log)
            session.commit()
    finally:
        await remove_run(run_id)


@router.post("/orchestrate")
def trigger_orchestration(payload: OrchestratePayload, background_tasks: BackgroundTasks):
    if not payload.worlds:
        raise HTTPException(status_code=400, detail="Must provide at least one target world name.")
        
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline_in_background, run_id, payload.worlds)
    return {"status": "started", "run_id": run_id, "worlds": payload.worlds}


@router.post("/tiering")
def trigger_tiering(background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_tiering_in_background, run_id)
    return {"status": "started", "run_id": run_id}

async def run_tiering_in_background(run_id: str):
    from app.agents.nodes import architecture_node
    from app.agents.state import OmniverseState
    from app.core.state import add_active_run, remove_run
    
    await add_active_run(run_id)
    
    with Session(engine) as session:
        # Prepare state with verified worlds
        verified_worlds = [u.name for u in session.exec(select(Universe).where(Universe.is_explored == True)).all()]
        
        # We need the consolidated dataset for architecture_node
        setting = session.get(Setting, "CONSOLIDATED_DATASET")
        dataset = setting.value if setting else ""
        
        state: OmniverseState = {
            "run_id": run_id,
            "target_worlds": [],
            "research_results": [],
            "verified_worlds": verified_worlds,
            "current_tier_system": None,
            "system_stable": False,
            "anomalies": [],
            "generated_theories": [],
            "errors": [],
            "architecture_retries": 0,
            "active_task": "ARCHITECTURE"
        }
        
        try:
            # Manually run the node
            await architecture_node(state)
        except Exception as e:
            print(f"[API] Error executing tiering: {e}")
        finally:
            await remove_run(run_id)


@router.post("/extrapolate")
def trigger_extrapolation(payload: ExtrapolatePayload, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        if payload.scope == "all":
            target_worlds = [u.name for u in session.exec(select(Universe).where(Universe.is_explored == True)).all()]
        elif payload.scope == "worlds":
            if not payload.worlds:
                raise HTTPException(status_code=400, detail="worlds list required for 'worlds' scope")
            
            # Verify that all requested worlds are actually explored/verified
            verified_names = [u.name for u in session.exec(select(Universe).where(Universe.is_explored == True)).all()]
            target_worlds = [w for w in payload.worlds if w in verified_names]
            
            if not target_worlds:
                return {"status": "noop", "message": "None of the specified worlds are verified."}
        elif payload.scope == "tier":
            if payload.tier is None:
                raise HTTPException(status_code=400, detail="tier value required for 'tier' scope")
            target_worlds = [u.name for u in session.exec(
                select(Universe).join(WorldTier).where(WorldTier.tier_number == payload.tier)
            ).all()]
        else:
            raise HTTPException(status_code=400, detail="Invalid scope")

    if not target_worlds:
        return {"status": "noop", "message": "No worlds matched the specified scope."}

    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_extrapolation_in_background, run_id, target_worlds)
    return {"status": "started", "run_id": run_id, "worlds": target_worlds}


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
            with Session(extrapolation_engine) as extra_session:
                theories = extra_session.exec(select(Theory).where(Theory.universe_id.in_(universe_ids))).all()
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
    with Session(extrapolation_engine) as session:
        theories = session.exec(select(Theory).order_by(Theory.created_at.desc())).all()
        return [{"id": t.id, "universe_id": t.universe_id, "theory": t.theory_text, "auditor_feedback": t.auditor_feedback, "created_at": str(t.created_at)} for t in theories]


@router.get("/model-status")
def model_status():
    with Session(engine) as session:
        routes = session.exec(select(AgentRouteFallback)).all()
        providers = {p.id: p for p in session.exec(select(ProviderConfig)).all()}
        route_status = []
        for route in routes:
            provider = providers.get(route.provider_id)
            route_status.append({
                "task_type": route.task_type,
                "configured": bool(provider and provider.provider_type and route.models),
                "provider": provider.name if provider else None,
                "models": route.models,
            })
        return {"initialized": True, "routes": route_status}


@router.get("/agent-activity")
async def agent_activity():
    with Session(engine) as session:
        logs = session.exec(select(ExecutionState).order_by(ExecutionState.created_at.desc()).limit(50)).all()
        active_runs = await get_active_runs()
        return {"active_runs": active_runs, "logs": [{"run_id": l.run_id, "node_name": l.node_name, "thought": l.thought, "status": l.status, "created_at": str(l.created_at)} for l in logs]}


@router.post("/reset-activity")
def reset_activity():
    return clear_logs()


@router.post("/abort")
async def abort_run_endpoint(payload: dict):
    run_id = payload.get("runId") or payload.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="runId required")
    await abort_run(run_id)
    with Session(engine) as session:
        session.add(ExecutionState(run_id=run_id, node_name="Manager", thought="Abort requested", status="ABORT_REQUESTED", state_snapshot="{}"))
        session.commit()
    return {"status": "abort_requested", "run_id": run_id}


@router.get("/logs/file")
def get_file_logs(
    limit: int = Query(100, ge=1, le=1000),
    filter: Optional[str] = None
):
    from app.core.agent_logger import LOG_FILE
    if not LOG_FILE.exists():
        return []
    
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
            
            # Read chunks from the end until we have enough lines
            buffer = b""
            pointer = file_size
            while pointer > 0 and len(buffer.split(b"\n")) <= limit + 1:
                read_size = min(pointer, 4096)
                pointer -= read_size
                f.seek(pointer)
                buffer = f.read(read_size) + buffer
            
            lines = buffer.decode("utf-8").splitlines()
            
            if filter:
                lines = [l for l in lines if filter.lower() in l.lower()]
            
            return lines[-limit:]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {str(e)}")

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
                    yield f"data: {json.dumps({'id': log.id, 'node_name': log.node_name, 'thought': log.thought, 'status': log.status, 'created_at': str(log.created_at)})}\n\n"
                    last_id = log.id
                    if log.status in {"FAILED", "ABORTED", "ABORT_REQUESTED"}:
                        yield f"data: {json.dumps({'finished': True, 'failed': True if log.status == 'FAILED' else False, 'aborted': True if log.status != 'FAILED' else False})}\n\n"
                        return
                    if log.status == "COMPLETED" and log.node_name in {"Ontological Theorist", "Focused Search"}:
                        yield "data: {\"finished\": true}\n\n"
                        return
            await asyncio.sleep(1)

    return StreamingResponse(log_generator(), media_type="text/event-stream")
