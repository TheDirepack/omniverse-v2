from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
from app.core.runtime_state import add_active_run, remove_run, abort_run, get_active_runs
from app.agents.workflow import app_graph
from app.services.execution_service import ExecutionService
from app.services.universe_service import UniverseService

router = APIRouter(prefix="/runs", tags=["runs"])

class OrchestratePayload(BaseModel):
    worlds: List[str]

class ExtrapolatePayload(BaseModel):
    scope: str = Field(..., pattern="^(all|worlds|tier)$")
    worlds: Optional[List[str]] = None
    tier: Optional[int] = None

class FocusedSearchPayload(BaseModel):
    worlds: List[str]
    features: List[str]

async def run_pipeline_in_background(run_id: str, target_worlds: List[str]):
    from app.core.agent_engine import run_fetch_cache
    from app.services.execution_service import ExecutionService
    from app.services.universe_service import UniverseService
    
    exec_service = ExecutionService()
    uni_service = UniverseService()
    
    from app.core.runtime_state import is_aborted
    if await is_aborted(run_id):
        exec_service.log_transition(run_id, "Manager", "Run aborted before initiation.", "FAILED", {})
        return
    
    for name in target_worlds:
        if not uni_service.get_universe(name):
            uni_service.create_universe(name)

    run_fetch_cache.clear()
    await add_active_run(run_id)
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
        "architecture_retries": 0,
        "architecture_attempts": 0
    }
    try:
        await app_graph.ainvoke(inputs)
    except Exception as e:
        exec_service.log_transition(run_id, "Manager", f"Critical Execution Failure: {str(e)}", "FAILED", {"error": str(e)})
    finally:
        await remove_run(run_id)

async def run_focused_search_in_background(run_id: str, target_worlds: List[str], focused_features: List[str]):
    from app.core.agent_engine import run_fetch_cache
    from app.services.execution_service import ExecutionService
    
    exec_service = ExecutionService()
    from app.core.runtime_state import is_aborted
    if await is_aborted(run_id):
        raise RuntimeError("Run aborted before start")
    
    run_fetch_cache.clear()
    await add_active_run(run_id)
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
    try:
        await app_graph.ainvoke(inputs)
    except Exception as e:
        exec_service.log_transition(run_id, "Focused Search", f"Focused search failed: {str(e)}", "FAILED", {"error": str(e)})
    finally:
        await remove_run(run_id)

async def run_tiering_in_background(run_id: str):
    from app.services.universe_service import UniverseService
    from app.services.settings_service import SettingsService
    from app.agents.nodes import architecture_node
    from app.agents.workflow_state import OmniverseState
    
    uni_service = UniverseService()
    settings_service = SettingsService()
    
    await add_active_run(run_id)
    verified_worlds = [u.name for u in uni_service.repo.get_all() if u.is_explored]
    
    setting = settings_service.repo.get_setting("CONSOLIDATED_DATASET")
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
        await architecture_node(state)
    except Exception as e:
        print(f"[API] Error executing tiering: {e}")
    finally:
        await remove_run(run_id)

async def run_extrapolation_in_background(run_id: str, target_worlds: List[str]):
    from app.core.agent_engine import run_fetch_cache
    run_fetch_cache.clear()
    await add_active_run(run_id)
    inputs = {
        "target_worlds": target_worlds,
        "verified_worlds": target_worlds,
        "run_id": run_id,
        "active_task": "EXTRAPOLATION",
        "generated_theories": [],
    }
    try:
        await app_graph.ainvoke(inputs)
    except Exception as e:
        from app.services.execution_service import ExecutionService
        exec_service = ExecutionService()
        exec_service.log_transition(run_id, "Manager", f"Critical Extrapolation Failure: {str(e)}", "FAILED", {"error": str(e)})
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

@router.post("/extrapolate")
def trigger_extrapolation(payload: ExtrapolatePayload, background_tasks: BackgroundTasks):
    from app.services.universe_service import UniverseService
    uni_service = UniverseService()
    
    if payload.scope == "all":
        target_worlds = [u.name for u in uni_service.repo.get_all() if u.is_explored]
    elif payload.scope == "worlds":
        if not payload.worlds:
            raise HTTPException(status_code=400, detail="worlds list required for 'worlds' scope")
        verified_names = [u.name for u in uni_service.repo.get_all() if u.is_explored]
        target_worlds = [w for w in payload.worlds if w in verified_names]
        if not target_worlds:
            return {"status": "noop", "message": "None of the specified worlds are verified."}
    elif payload.scope == "tier":
        if payload.tier is None:
            raise HTTPException(status_code=400, detail="tier value required for 'tier' scope")
        from app.services.tiering_service import TieringService
        tier_service = TieringService()
        # Use repo for complex join
        from sqlmodel import Session, select
        from app.db.session import engine
        from app.db.schema import Universe, WorldTier
        with Session(engine) as session:
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

@router.post("/focused-search")
def focused_search(payload: FocusedSearchPayload, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_focused_search_in_background, run_id, payload.worlds, payload.features)
    return {"status": "started", "run_id": run_id, "worlds": payload.worlds, "features": payload.features}

@router.post("/abort")
async def abort_run_endpoint(payload: dict):
    run_id = payload.get("runId") or payload.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="runId required")
    await abort_run(run_id)
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    exec_service.log_transition(run_id, "Manager", "Abort requested", "ABORT_REQUESTED", {})
    return {"status": "abort_requested", "run_id": run_id}

@router.get("/agent-activity")
async def agent_activity():
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    logs = exec_service.repo.get_recent_logs()
    active_runs = await get_active_runs()
    return {"active_runs": active_runs, "logs": [{"run_id": l.run_id, "node_name": l.node_name, "thought": l.thought, "status": l.status, "created_at": str(l.created_at)} for l in logs]}

@router.post("/reset-activity")
def reset_activity():
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    exec_service.clear_logs()
    return {"status": "success"}

@router.get("/logs/file")
def get_file_logs(limit: int = 100, filter: Optional[str] = None):
    from app.core.agent_logger import LOG_FILE
    from pathlib import Path
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()
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
    from fastapi.responses import StreamingResponse
    async def log_generator():
        from app.services.execution_service import ExecutionService
        exec_service = ExecutionService()
        last_id = 0
        while True:
            new_logs = exec_service.repo.get_logs_for_run(run_id, last_id)
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
