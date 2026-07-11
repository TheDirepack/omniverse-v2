import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.runtime_state import get_active_runs
from app.core.templates import templates
from app.services.research_workspace import WorkspaceService
from app.services.universe_service import UniverseService

# Remove _filter_worlds as it's now in UniverseService


def _render_worlds(
    request: Request,
    worlds: Sequence[Any],
    q: str = "",
    explored: str = "",
    franchise: str = "",
    batch_started: int | None = None,
) -> HTMLResponse:
    uni_service = UniverseService()
    filtered = uni_service.filter_universes(
        worlds, q=q, explored=explored, franchise=franchise
    )
    template = templates.env.get_template("fragments/database_worlds.html")
    return HTMLResponse(content=template.render(
        request=request, worlds=filtered, q=q, explored=explored, franchise=franchise,
        batch_started=batch_started,
    ))

router = APIRouter(tags=["research_views"])


@router.get("/", response_class=HTMLResponse)
async def research_page(request: Request):
    # Redirect to choose-world if no active world is set (via cookie)
    active_world = request.cookies.get("active_world_id")
    if not active_world:
        return RedirectResponse(url="/research/choose-world", status_code=302)

    uni_service = UniverseService()
    world = uni_service.get_universe_by_uuid(active_world)
    if not world:
        return RedirectResponse(url="/research/choose-world", status_code=302)

    template = templates.env.get_template("pages/research.html")
    return HTMLResponse(content=template.render(request=request, world=world))


@router.get("/choose-world", response_class=HTMLResponse)
async def choose_world_page(request: Request):
    uni_service = UniverseService()
    universes = uni_service.get_all_universes(limit=5000)
    template = templates.env.get_template("pages/choose_world.html")
    return HTMLResponse(content=template.render(request=request, universes=universes))




@router.get("/queue", response_class=HTMLResponse)
async def research_queue(request: Request):
    active_run_ids = await get_active_runs()
    template = templates.env.get_template("fragments/research_queue.html")
    return HTMLResponse(
        content=template.render(request=request, active_run_ids=active_run_ids)
    )


@router.get("/focused-search", response_class=HTMLResponse)
async def focused_search_fragment(request: Request):
    template = templates.env.get_template("fragments/focused_search_panel.html")
    return HTMLResponse(content=template.render(request=request))


@router.post("/focused-search", response_class=HTMLResponse)
async def focused_search_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    worlds: str = Form(...),
    features: str = Form(...),
):
    from app.api.routers.runs import run_focused_search_in_background

    world_list = [w.strip() for w in worlds.split(",") if w.strip()]
    feature_list = [f.strip() for f in features.split(",") if f.strip()]

    results = []
    if world_list and feature_list:
        run_id = str(uuid.uuid4())
        background_tasks.add_task(
            run_focused_search_in_background, run_id, world_list, feature_list
        )
        results = [
            f"Focused search started for {len(world_list)} world(s): "
            f"{', '.join(world_list)}"
        ]
    else:
        results = ["Provide at least one world and one feature."]

    template = templates.env.get_template("fragments/focused_search_panel.html")
    return HTMLResponse(
        content=template.render(request=request, results=results)
    )


@router.get("/workspace/notebook", response_class=HTMLResponse)
async def workspace_notebook(request: Request):
    active_world = request.cookies.get("active_world_id")
    if not active_world:
        return HTMLResponse(content="No active world set.", status_code=400)

    uni_service = UniverseService()
    world = uni_service.get_universe_by_uuid(active_world)
    if not world:
        return HTMLResponse(content="World not found.", status_code=404)

    workspace_service = WorkspaceService()
    entries = workspace_service.get_notebook_index(world.uuid)

    template = templates.env.get_template("fragments/research_notebook.html")
    return HTMLResponse(
        content=template.render(request=request, world=world, entries=entries)
    )


@router.get("/workspace/notebook/{entry_id}", response_class=HTMLResponse)
async def workspace_notebook_entry(request: Request, entry_id: int):
    workspace_service = WorkspaceService()
    entry = workspace_service.get_notebook_entry(entry_id)
    if not entry:
        return HTMLResponse(content="Entry not found.", status_code=404)

    template = templates.env.get_template("fragments/research_notebook_entry.html")
    return HTMLResponse(content=template.render(request=request, entry=entry))


@router.get("/workspace/sources", response_class=HTMLResponse)
async def workspace_sources(request: Request):
    active_world = request.cookies.get("active_world_id")
    if not active_world:
        return HTMLResponse(content="No active world set.", status_code=400)

    uni_service = UniverseService()
    world = uni_service.get_universe_by_uuid(active_world)
    if not world:
        return HTMLResponse(content="World not found.", status_code=404)

    workspace_service = WorkspaceService()
    sources = workspace_service.get_sources(world.uuid)

    template = templates.env.get_template("fragments/research_sources.html")
    return HTMLResponse(
        content=template.render(request=request, world=world, sources=sources)
    )


@router.get("/workspace/timeline", response_class=HTMLResponse)
async def workspace_timeline(request: Request):
    active_world = request.cookies.get("active_world_id")
    if not active_world:
        return HTMLResponse(content="No active world set.", status_code=400)

    uni_service = UniverseService()
    world = uni_service.get_universe_by_uuid(active_world)
    if not world:
        return HTMLResponse(content="World not found.", status_code=404)

    workspace_service = WorkspaceService()
    timeline = workspace_service.get_timeline(world.uuid)

    template = templates.env.get_template("fragments/research_timeline.html")
    return HTMLResponse(
        content=template.render(request=request, world=world, timeline=timeline)
    )
