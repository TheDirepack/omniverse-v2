import asyncio
import json
import re
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.agents.nodes import architecture_node
from app.agents.workflow import app_graph
from app.agents.workflow_state import OmniverseState
from app.core.agent_logger import LOG_FILE
from app.core.domain import ResearchTarget
from app.core.enums import RunPhase
from app.core.runtime_state import (
    abort_run,
    add_active_run,
    get_active_runs,
    is_aborted,
    remove_run,
)
from app.core.templates import templates
from app.db.notebook_schema import AcquisitionArtifact, WorldAcquisitionUsage
from app.db.notebook_session import notebook_engine
from app.db.schema import ExecutionState, Universe, WorldTier
from app.db.session import engine
from app.repositories.execution import ExecutionRepository
from app.services.execution_service import ExecutionService
from app.services.universe_service import UniverseService

router = APIRouter(tags=["runs"])


class OrchestratePayload(BaseModel):
    universe_uuids: list[str]


class ExtrapolatePayload(BaseModel):
    scope: str = Field(..., pattern="^(all|worlds|tier)$")
    worlds: list[str] | None = None
    tier: int | None = None


class FocusedSearchPayload(BaseModel):
    universe_uuids: list[str]
    features: list[str]


class AbortRunPayload(BaseModel):
    run_id: str = Field(..., min_length=1, alias="runId")

    class Config:
        populate_by_name = True


class AgentLogResponse(BaseModel):
    run_id: str
    node_name: str
    thought: str | None = None
    status: str
    created_at: str


class AgentActivityResponse(BaseModel):
    active_runs: list[str]
    logs: list[AgentLogResponse]


async def run_pipeline_in_background(run_id: str, universe_uuids: list[str]):
    exec_service = ExecutionService()
    uni_service = UniverseService()

    if await is_aborted(run_id):
        exec_service.log_transition(
            run_id, "Manager", "Run aborted before initiation.", RunPhase.FAILED, {}
        )
        return

    # Resolve UUIDs to ResearchTarget domain objects
    target_worlds = []
    for uuid_val in universe_uuids:
        u = uni_service.get_universe_by_uuid(uuid_val)
        if u:
            metadata = uni_service.get_universe_metadata(u.id)
            target_worlds.append(ResearchTarget(
                uuid=u.uuid,
                name=u.name,
                franchise=metadata.get("franchise"),
                continuity=metadata.get("continuity"),
                era=metadata.get("era"),
                slug=u.slug,
                parent_id=u.parent_id
            ))

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
        "active_task": RunPhase.RESEARCH,
        "errors": [],
        "architecture_retries": 0,
        "architecture_attempts": 0,
    }
    try:
        await app_graph.ainvoke(inputs)
    except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, OSError) as e:
        exec_service.log_transition(
            run_id,
            "Manager",
            f"Critical Extrapolation Failure: {e!s}",
            RunPhase.FAILED,
            {"error": str(e)},
        )

    finally:
        await remove_run(run_id)


async def run_focused_search_in_background(
    run_id: str, universe_uuids: list[str], focused_features: list[str]
):
    exec_service = ExecutionService()
    uni_service = UniverseService()

    if await is_aborted(run_id):
        raise RuntimeError(
            "Run aborted before start"
        )

    # Resolve UUIDs to ResearchTarget domain objects
    target_worlds = []
    for uuid_val in universe_uuids:
        u = uni_service.get_universe_by_uuid(uuid_val)
        if u:
            metadata = uni_service.get_universe_metadata(u.id)
            target_worlds.append(ResearchTarget(
                uuid=u.uuid,
                name=u.name,
                franchise=metadata.get("franchise"),
                continuity=metadata.get("continuity"),
                era=metadata.get("era"),
                slug=u.slug,
                parent_id=u.parent_id
            ))

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
        "active_task": RunPhase.RESEARCH,
        "errors": [],
        "architecture_retries": 0,
    }
    try:
        await app_graph.ainvoke(inputs)
    except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, OSError) as e:
        exec_service.log_transition(
            run_id,
            "Focused Search",
            f"Focused search failed: {e!s}",
            RunPhase.FAILED,
            {"error": str(e)},
        )

    finally:
        await remove_run(run_id)


async def run_tiering_in_background(run_id: str):
    uni_service = UniverseService()
    exec_service = ExecutionService()

    if await is_aborted(run_id):
        exec_service.log_transition(
            run_id, "Manager", "Run aborted before initiation.", RunPhase.FAILED, {}
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
        "active_task": RunPhase.ARCHITECTURE,
    }
    try:
        await architecture_node(state)
    except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, OSError) as e:
        print(f"[API] Error executing tiering: {e}")
        exec_service = ExecutionService()
        exec_service.log_transition(
            run_id, "Manager",
            f"Critical Tiering Failure: {e!s}",
            RunPhase.FAILED,
            {"error": str(e)},
        )
        exec_service.close()
    finally:
        await remove_run(run_id)


async def run_extrapolation_in_background(run_id: str, target_worlds: list[str]):
    await add_active_run(run_id)
    inputs = {
        "target_worlds": target_worlds,
        "verified_worlds": target_worlds,
        "run_id": run_id,
        "active_task": RunPhase.EXTRAPOLATION,
        "generated_theories": [],
    }
    try:
        await app_graph.ainvoke(inputs)
    except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, OSError) as e:
        exec_service = ExecutionService()
        exec_service.log_transition(
            run_id,
            "Manager",
            f"Critical Extrapolation Failure: {e!s}",
            RunPhase.FAILED,
            {"error": str(e)},
        )

    finally:
        await remove_run(run_id)


@router.post("/start")
async def trigger_start(
    request: Request, background_tasks: BackgroundTasks
):
    import json as _json

    uuids: list[str] = []
    content_type = request.headers.get("content-type", "")
    if "json" in content_type.lower():
        body = await request.json()
        uuids = body.get("payload") or body.get("universe_uuids") or []
    else:
        form = await request.form()
        raw = form.get("payload", "[]")
        uuids = _json.loads(raw) if raw.startswith("[") else [raw]

    if not uuids:
        raise HTTPException(
            status_code=400, detail="Must provide at least one target universe UUID."
        )
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_pipeline_in_background, run_id, uuids)
    return {"status": "started", "run_id": run_id, "uuids": uuids}


@router.post("/workflow")
def trigger_orchestration(
    payload: OrchestratePayload, background_tasks: BackgroundTasks
):
    if not payload.universe_uuids:
        raise HTTPException(
            status_code=400, detail="Must provide at least one target universe UUID."
        )
    run_id = str(uuid.uuid4())
    background_tasks.add_task(
        run_pipeline_in_background, run_id, payload.universe_uuids
    )
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
        verified_names = [
            u.name for u in uni_service.get_all_universes() if u.is_explored
        ]
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
        run_focused_search_in_background,
        run_id,
        payload.universe_uuids,
        payload.features,
    )
    return {
        "status": "started",
        "run_id": run_id,
        "uuids": payload.universe_uuids,
        "features": payload.features,
    }


@router.post("/abort")
async def abort_run_endpoint(request: Request):
    run_id = None
    try:
        body = await request.json()
        run_id = body.get("runId") or body.get("run_id") or body.get("runid")
    except (ValueError, TypeError, KeyError):
        try:
            form = await request.form()
            run_id = form.get("runId") or form.get("run_id") or form.get("runid")
        except (ValueError, TypeError, KeyError):
            pass

    if not run_id:
        raise HTTPException(status_code=422, detail="Missing run_id")

    await abort_run(run_id)
    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id, "Manager", "Abort requested", RunPhase.ABORT_REQUESTED, {}
    )

    return {"status": "abort_requested", "run_id": run_id}


@router.post("/abort-all")
async def abort_all_runs():
    active_runs = await get_active_runs()
    for run_id in active_runs:
        await abort_run(run_id)

    exec_service = ExecutionService()
    for run_id in active_runs:
        exec_service.log_transition(
            run_id, "Manager", "Global abort requested", RunPhase.ABORT_REQUESTED, {}
        )

    return {"status": "all_aborted", "count": len(active_runs)}


@router.get("/active-detailed")
async def get_active_runs_detailed(request: Request, filter: str | None = None):
    active_ids = await get_active_runs()
    detailed_runs = []

    with Session(engine) as session:
        for rid in active_ids:
            latest = session.exec(
                select(ExecutionState)
                .where(ExecutionState.run_id == rid)
                .order_by(ExecutionState.created_at.desc())
                .limit(1)
            ).first()

            if not latest:
                continue

            try:
                state = json.loads(latest.state_snapshot)
                target_worlds = state.get("target_worlds", [])
                world_name = ", ".join(target_worlds) if target_worlds else "Unknown"
                focus = state.get("focused_features", ["General Research"])
                focus_str = ", ".join(focus) if isinstance(focus, list) else str(focus)
            except (json.JSONDecodeError, TypeError, KeyError, AttributeError):
                world_name = "Unknown"
                focus_str = "Unknown"

            if filter and filter.lower() not in world_name.lower() and filter.lower() not in focus_str.lower():
                continue

            # Simple progress estimation based on phase
            phase = latest.status
            progress = 0
            if phase == RunPhase.RESEARCH: progress = 30
            elif phase == RunPhase.INTEGRATING: progress = 60
            elif phase == RunPhase.SUMMARIZING: progress = 90
            elif phase == RunPhase.COMPLETED: progress = 100

            detailed_runs.append({
                "run_id": rid,
                "world": world_name,
                "focus": focus_str,
                "progress": progress,
                "status": phase
            })

    template = templates.env.get_template("components/active_runs_table.html")
    return HTMLResponse(content=template.render(request=request, runs=detailed_runs))


@router.get("/agent-activity", response_model=AgentActivityResponse)
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
        try:
            state = json.loads(run.state_snapshot)
            target_worlds = state.get("target_worlds", [])
            goal = ", ".join(target_worlds) if target_worlds else "Unknown Goal"
        except (json.JSONDecodeError, TypeError, AttributeError):
            goal = "Unknown Goal"

        results.append({
            "run_id": run.run_id,
            "world": goal,
            "status": run.status,
            "node": run.node_name,
            "created_at": str(run.created_at),
        })

    template = templates.env.get_template("components/research_history.html")
    return HTMLResponse(content=template.render(request=request, runs=results))


@router.get("/{run_id}", response_class=HTMLResponse)
async def run_details(request: Request, run_id: str):
    template = templates.env.get_template("pages/run_details.html")
    return HTMLResponse(content=template.render(
        request=request, run_id=run_id, current_path=str(request.url.path)
    ))


@router.get("/{run_id}/acquisition", response_class=HTMLResponse)
async def run_acquisition(request: Request, run_id: str):
    with Session(notebook_engine) as session:
        stmt = (
            select(AcquisitionArtifact)
            .join(WorldAcquisitionUsage)
            .where(WorldAcquisitionUsage.run_id == run_id)
            .order_by(WorldAcquisitionUsage.created_at)
        )
        artifacts = session.exec(stmt).all()

    template = templates.env.get_template("components/acquisition_panel.html")
    return HTMLResponse(
        content=template.render(
            request=request, artifacts=artifacts, run_id=run_id
        )
    )


@router.get("/{run_id}/phase-details", response_class=HTMLResponse)
async def run_phase_details(request: Request, run_id: str):
    with Session(engine) as session:
        last_state = session.exec(
            select(ExecutionState)
            .where(ExecutionState.run_id == run_id)
            .order_by(ExecutionState.created_at.desc())
            .limit(1)
        ).first()

    if not last_state:
        return HTMLResponse(
            "<p class='text-gray-500 italic'>No execution state found for this run.</p>",
            status_code=404,
        )

    template = templates.env.get_template("components/run_phase_details.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            status=last_state.status,
            state_snapshot=last_state.state_snapshot
        )
    )


LOG_LINE_RE = re.compile(
    r"^\[(.+?)\] \[(.+?)\] \[(.+?)\] \[(.+?)\] \[(.+?)\] \[([\w.]+)\] (.+)$"
)


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
    if not LOG_FILE.exists():
        return {"logs": [], "total": 0, "has_more": False}
    try:
        has_filters = any([filter, agent, world, model, event_type, tool])
        with LOG_FILE.open(encoding="utf-8") as f:
            lines = f.readlines()

        results = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            m = LOG_LINE_RE.match(line)
            if not m:
                if filter and filter.lower() not in line.lower():
                    continue
                results.append(line)
                continue

            log_agent = m.group(2)
            log_model = m.group(3)
            log_world = m.group(5)
            log_type = m.group(6).removeprefix("AgentEventType.")
            log_content = m.group(7)

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
    except (ValueError, TypeError, KeyError, IndexError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {e!s}") from e


@router.get("/logs/{run_id}")
async def get_realtime_logs(run_id: str):
    async def log_generator():
        exec_service = ExecutionService()
        last_id = 0
        try:
            while True:
                new_logs = exec_service.repo.get_logs_for_run(run_id, last_id)
                for log in new_logs:
                    yield f"data: {json.dumps({'id': log.id, 'node_name': log.node_name, 'thought': log.thought, 'status': log.status, 'created_at': str(log.created_at)})}\n\n"
                    last_id = log.id
                    if log.status in {RunPhase.FAILED, RunPhase.ABORT_REQUESTED}:

                        yield f"data: {json.dumps({'finished': True, 'failed': log.status == RunPhase.FAILED, 'aborted': log.status != RunPhase.FAILED})}\n\n"
                        return
                    if log.status == RunPhase.COMPLETED and log.node_name in {
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


@router.delete("/claims")
async def delete_all_claims():
    with Session() as session:
        repo = ExecutionRepository(session)
        result = repo.delete_all_claims()
        print(f"Delete result: {result}")

    return {"detail": "All claims deleted"}
