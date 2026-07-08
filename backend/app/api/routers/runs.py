import asyncio
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.agents.workflow import app_graph
from app.core.runtime_state import (
    abort_run,
    add_active_run,
    get_active_runs,
    remove_run,
)
from app.services.execution_service import ExecutionService
from app.services.universe_service import UniverseService

router = APIRouter(prefix="/runs", tags=["runs"])


class OrchestratePayload(BaseModel):
    universe_uuids: list[str]


class ExtrapolatePayload(BaseModel):
    scope: str = Field(..., pattern="^(all|worlds|tier)$")
    worlds: list[str] | None = None
    tier: int | None = None


class FocusedSearchPayload(BaseModel):
    universe_uuids: list[str]
    features: list[str]


async def run_pipeline_in_background(run_id: str, universe_uuids: list[str]):
    exec_service = ExecutionService()
    uni_service = UniverseService()

    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        exec_service.log_transition(
            run_id, "Manager", "Run aborted before initiation.", "FAILED", {}
        )
        return

    # Resolve UUIDs to names for the pipeline state
    target_worlds = []
    for uuid in universe_uuids:
        universe = uni_service.get_universe_by_uuid(uuid)
        if universe:
            target_worlds.append(universe.name)
        else:
            # This should technically not happen if the UI passes valid UUIDs,
            # but we handle it gracefully.
            pass

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
        "architecture_attempts": 0,
    }
    try:
        await app_graph.ainvoke(inputs)
    except Exception as e:
        exec_service.log_transition(
            run_id,
            "Manager",
            f"Critical Execution Failure: {e!s}",
            "FAILED",
            {"error": str(e)},
        )
    finally:
        await remove_run(run_id)


async def run_focused_search_in_background(
    run_id: str, universe_uuids: list[str], focused_features: list[str]
):
    exec_service = ExecutionService()
    uni_service = UniverseService()
    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        raise RuntimeError("Run aborted before start")
    
    # Resolve UUIDs to names
    target_worlds = []
    for uuid in universe_uuids:
        universe = uni_service.get_universe_by_uuid(uuid)
        if universe:
            target_worlds.append(universe.name)

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
        "architecture_retries": 0,
    }
    try:
        await app_graph.ainvoke(inputs)
    except Exception as e:
        exec_service.log_transition(
            run_id,
            "Focused Search",
            f"Focused search failed: {e!s}",
            "FAILED",
            {"error": str(e)},
        )
    finally:
        await remove_run(run_id)


async def run_tiering_in_background(run_id: str):
    from app.agents.nodes import architecture_node
    from app.agents.workflow_state import OmniverseState
    from app.core.runtime_state import is_aborted

    uni_service = UniverseService()
    exec_service = ExecutionService()

    if await is_aborted(run_id):
        exec_service.log_transition(
            run_id, "Manager", "Run aborted before initiation.", "FAILED", {}
        )
        return

    await add_active_run(run_id)
    verified_worlds = [u.name for u in uni_service.get_all_universes() if u.is_explored]

    state: OmniverseState = {
        "run_id": run_id,
        "target_worlds": [],
        "focused_features": [],
        "is_focused_search": False,
        "research_results": [],
        "verified_worlds": verified_worlds,
        "current_tier_system": None,
        "system_stable": False,
        "anomalies": [],
        "generated_theories": [],
        "errors": [],
        "architecture_retries": 0,
        "architecture_attempts": 0,
        "active_task": "ARCHITECTURE",
    }
    try:
        await architecture_node(state)
    except Exception as e:
        print(f"[API] Error executing tiering: {e}")
    finally:
        await remove_run(run_id)


async def run_extrapolation_in_background(run_id: str, target_worlds: list[str]):
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
        exec_service.log_transition(
            run_id,
            "Manager",
            f"Critical Extrapolation Failure: {e!s}",
            "FAILED",
            {"error": str(e)},
        )
    finally:
        await remove_run(run_id)


@router.post("/orchestrate")
def trigger_orchestration(
    payload: OrchestratePayload, background_tasks: BackgroundTasks
):
    if not payload.universe_uuids:
        raise HTTPException(
            status_code=400, detail="Must provide at least one target universe UUID."
        )
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline_in_background, run_id, payload.universe_uuids)
    return {"status": "started", "run_id": run_id, "uuids": payload.universe_uuids}


@router.post("/tiering")
def trigger_tiering(background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_tiering_in_background, run_id)
    return {"status": "started", "run_id": run_id}


@router.post("/extrapolate")
def trigger_extrapolation(
    payload: ExtrapolatePayload, background_tasks: BackgroundTasks
):
    uni_service = UniverseService()

    if payload.scope == "all":
        target_worlds = [
            u.name for u in uni_service.get_all_universes() if u.is_explored
        ]
    elif payload.scope == "worlds":
        if not payload.worlds:
            raise HTTPException(
                status_code=400, detail="worlds list required for 'worlds' scope"
            )
        verified_names = [u.name for u in uni_service.get_all_universes() if u.is_explored]
        target_worlds = [w for w in payload.worlds if w in verified_names]
        if not target_worlds:
            return {
                "status": "noop",
                "message": "None of the specified worlds are verified.",
            }
    elif payload.scope == "tier":
        if payload.tier is None:
            raise HTTPException(
                status_code=400, detail="tier value required for 'tier' scope"
            )
        # Use repo for complex join
        from sqlmodel import Session, select

        from app.db.schema import Universe, WorldTier
        from app.db.session import engine

        with Session(engine) as session:
            target_worlds = [
                u.name
                for u in session.exec(
                    select(Universe)
                    .join(WorldTier)
                    .where(WorldTier.tier_number == payload.tier)
                ).all()
            ]
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
    background_tasks.add_task(
        run_focused_search_in_background, run_id, payload.universe_uuids, payload.features
    )
    return {
        "status": "started",
        "run_id": run_id,
        "uuids": payload.universe_uuids,
        "features": payload.features,
    }


@router.post("/abort")
async def abort_run_endpoint(payload: dict):
    run_id = payload.get("runId") or payload.get("run_id")
    if not run_id:
        raise HTTPException(status_code=400, detail="runId required")
    await abort_run(run_id)
    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id, "Manager", "Abort requested", "ABORT_REQUESTED", {}
    )
    return {"status": "abort_requested", "run_id": run_id}


@router.get("/agent-activity")
async def agent_activity():
    exec_service = ExecutionService()
    logs = exec_service.repo.get_recent_logs()
    active_runs = await get_active_runs()
    return {
        "active_runs": active_runs,
        "logs": [
            {
                "run_id": log.run_id,
                "node_name": log.node_name,
                "thought": log.thought,
                "status": log.status,
                "created_at": str(log.created_at),
            }
            for log in logs
        ],
    }


@router.post("/reset-activity")
def reset_activity():
    exec_service = ExecutionService()
    exec_service.clear_logs()
    return {"status": "success"}


@router.get("/history", response_class=HTMLResponse)
async def runs_history(request: Request):
    exec_service = ExecutionService()
    runs = exec_service.repo.get_all_runs()
    
    results = []
    for run in runs:
        import json
        try:
            state = json.loads(run.state_snapshot)
            target_worlds = state.get("target_worlds", [])
            goal = ", ".join(target_worlds) if target_worlds else "Unknown Goal"
        except:
            goal = "Unknown Goal"
            
        results.append({
            "run_id": run.run_id,
            "world": goal,
            "status": run.status,
            "node": run.node_name,
            "created_at": str(run.created_at),
        })
    
    template = templates.env.get_template("fragments/research_history.html")
    return HTMLResponse(content=template.render(request=request, runs=results))


@router.get("/{run_id}", response_class=HTMLResponse)
async def run_details(request: Request, run_id: str):
    template = templates.env.get_template("pages/run_details.html")
    return HTMLResponse(content=template.render(request=request, run_id=run_id))


@router.get("/{run_id}/acquisition", response_class=HTMLResponse)
async def run_acquisition(request: Request, run_id: str):
    from app.db.unconfirmed_session import unconfirmed_session_factory
    from app.db.schema import WorldAcquisitionUsage, AcquisitionArtifact
    from sqlmodel import Session, select

    with Session(unconfirmed_session_factory()) as session:
        stmt = (
            select(AcquisitionArtifact)
            .join(WorldAcquisitionUsage)
            .where(WorldAcquisitionUsage.run_id == run_id)
            .order_by(WorldAcquisitionUsage.created_at)
        )
        artifacts = session.exec(stmt).all()

    template = templates.env.get_template("fragments/acquisition_panel.html")
    return HTMLResponse(content=template.render(request=request, artifacts=artifacts, run_id=run_id))

@router.get("/logs/file")
def get_file_logs(
    limit: int | None = 100,
    offset: int | None = 0,
    filter: str | None = None,
    agent: str | None = None,
    world: str | None = None,
    model: str | None = None,
    event_type: str | None = None,
    tool: str | None = None,
):
    from app.core.agent_logger import LOG_FILE
    from app.services.settings_service import SettingsService

    if not LOG_FILE.exists():
        return {"logs": [], "total": 0, "has_more": False}
    try:
        has_filters = any([filter, agent, world, model, event_type, tool])

        with open(LOG_FILE, encoding="utf-8") as f:
            lines = f.readlines()

        settings_service = SettingsService()
        hide_webfetch = settings_service.get_setting("HIDE_WEBFETCH_CONTENT")
        hide_websearch = settings_service.get_setting("HIDE_WEBSEARCH_CONTENT")

        # Normalize to boolean
        hide_webfetch = (
            hide_webfetch.value.lower() == "true" if hide_webfetch else False
        )
        hide_websearch = (
            hide_websearch.value.lower() == "true" if hide_websearch else False
        )

        results = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split("] ")
            if len(parts) < 6:
                if filter and filter.lower() not in line.lower():
                    continue
                results.append(line)
                continue

            log_agent = parts[1].strip("[")
            log_model = parts[2].strip("[")
            log_world = parts[4].strip("[")
            log_type = parts[5].strip("[")
            log_content = " ".join(parts[6:])

            if log_type == "TOOL_RES":
                if hide_webfetch and "Observation from webFetch:" in log_content:
                    log_content = "Observation from webFetch: [Content Hidden]"
                    line = "] ".join(parts[:6]) + "] " + log_content
                elif hide_websearch and "Observation from webSearch:" in log_content:
                    log_content = "Observation from webSearch: [Content Hidden]"
                    line = "] ".join(parts[:6]) + "] " + log_content

            if agent and agent.lower() not in log_agent.lower():
                continue
            if world and world.lower() not in log_world.lower():
                continue
            if model and model.lower() not in log_model.lower():
                continue
            if event_type and event_type.upper() != log_type.upper():
                continue
            if filter and filter.lower() not in line.lower():
                continue
            if tool and tool.lower() not in log_content.lower():
                continue

            results.append(line)

        total = len(results)

        if not has_filters:
            # Tail read logic: return most recent first
            # offset 0, limit 100 -> results[total-100 : total]
            end_idx = total - (offset or 0)
            start_idx = total - ((offset or 0) + (limit or 100))
            sliced_logs = results[max(0, start_idx) : max(0, end_idx)]
        else:
            # Filtered logs: return in chronological order
            sliced_logs = results[(offset or 0) : (offset or 0) + (limit or 100)]

        return {
            "logs": sliced_logs,
            "total": total,
            "has_more": (total - ((offset or 0) + (limit or 100)) > 0)
            if not has_filters
            else ((offset or 0) + (limit or 100) < total),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {e!s}")


@router.get("/logs/{run_id}")
async def get_realtime_logs(run_id: str):
    from fastapi.responses import StreamingResponse

    async def log_generator():
        exec_service = ExecutionService()
        last_id = 0
        try:
            while True:
                new_logs = exec_service.repo.get_logs_for_run(run_id, last_id)
                for log in new_logs:
                    yield f"data: {json.dumps({'id': log.id, 'node_name': log.node_name, 'thought': log.thought, 'status': log.status, 'created_at': str(log.created_at)})}\n\n"
                    last_id = log.id
                    if log.status in {"FAILED", "ABORT_REQUESTED"}:
                        yield f"data: {json.dumps({'finished': True, 'failed': log.status == 'FAILED', 'aborted': log.status != 'FAILED'})}\n\n"
                        return
                    if log.status == "COMPLETED" and log.node_name in {
                        "Ontological Theorist",
                        "Focused Search",
                    }:
                        yield 'data: {"finished": true}\n\n'
                        return
                await asyncio.sleep(1)
        finally:
            # Cleanup if needed
            pass

    return StreamingResponse(log_generator(), media_type="text/event-stream")
