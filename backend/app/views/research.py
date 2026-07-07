from collections.abc import Sequence
from typing import Any

import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Form, Query, Request
from fastapi.responses import HTMLResponse

from app.core.runtime_state import get_active_runs
from app.core.templates import templates
from app.services.universe_service import UniverseService


def _filter_worlds(
    worlds: Sequence[Any],
    q: str = "",
    explored: str = "",
    franchise: str = "",
) -> list[Any]:
    result = list(worlds)
    if q:
        q_lower = q.lower()
        result = [w for w in result if q_lower in w.name.lower()]
    if explored == "yes":
        result = [w for w in result if w.is_explored]
    elif explored == "no":
        result = [w for w in result if not w.is_explored]
    if franchise:
        f_lower = franchise.lower()
        result = [w for w in result if w.franchise and f_lower in w.franchise.lower()]
    return result


def _render_worlds(
    request: Request,
    worlds: Sequence[Any],
    q: str = "",
    explored: str = "",
    franchise: str = "",
    batch_started: int | None = None,
) -> HTMLResponse:
    filtered = _filter_worlds(worlds, q=q, explored=explored, franchise=franchise)
    template = templates.env.get_template("fragments/database_worlds.html")
    return HTMLResponse(content=template.render(
        request=request, worlds=filtered, q=q, explored=explored, franchise=franchise,
        batch_started=batch_started,
    ))

router = APIRouter(tags=["research_views"])


@router.get("/", response_class=HTMLResponse)
async def research_page(request: Request):
    uni_service = UniverseService()
    universes = uni_service.get_all_universes(limit=5000)
    template = templates.env.get_template("pages/research.html")
    return HTMLResponse(content=template.render(request=request, universes=universes))


@router.get("/database-worlds", response_class=HTMLResponse)
async def database_worlds(
    request: Request,
    q: str = Query(default=""),
    explored: str = Query(default=""),
    franchise: str = Query(default=""),
):
    uni_service = UniverseService()
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds, q=q, explored=explored, franchise=franchise)


@router.post("/add-world", response_class=HTMLResponse)
async def add_world(
    request: Request,
    background_tasks: BackgroundTasks,
    world_name: str = Form(...),
    auto_research: str = Form(default="false"),
    franchise: str = Form(default=""),
    category: str = Form(default=""),
    continuity: str = Form(default=""),
    era: str = Form(default=""),
    parent_id: int = Form(default=None),
):
    uni_service = UniverseService()
    existing = uni_service.get_universe(world_name)
    if not existing:
        uni_service.create_universe(
            name=world_name,
            franchise=franchise or None,
            category=category or None,
            continuity=continuity or None,
            era=era or None,
            parent_id=parent_id,
        )

    if auto_research == "true":
        from app.api.routers.runs import run_pipeline_in_background

        run_id = str(uuid.uuid4())
        background_tasks.add_task(
            run_pipeline_in_background, run_id, [world_name]
        )

    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)


@router.post("/batch-research", response_class=HTMLResponse)
async def batch_research(
    request: Request,
    background_tasks: BackgroundTasks,
    world_names: str = Form(...),
):
    from app.api.routers.runs import run_pipeline_in_background

    names = [w.strip() for w in world_names.split(",") if w.strip()]
    for name in names:
        run_id = str(uuid.uuid4())
        background_tasks.add_task(run_pipeline_in_background, run_id, [name])

    uni_service = UniverseService()
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds, batch_started=len(names))


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
            f"Focused search started for {len(world_list)} world(s): {', '.join(world_list)}"
        ]
    else:
        results = ["Provide at least one world and one feature."]

    template = templates.env.get_template("fragments/focused_search_panel.html")
    return HTMLResponse(
        content=template.render(request=request, results=results)
    )


@router.post("/worlds/{world_id}/toggle-explored", response_class=HTMLResponse)
async def toggle_explored(request: Request, world_id: int):
    uni_service = UniverseService()
    uni_service.reset_explored(world_id)
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)


@router.post("/worlds/{world_id}/delete", response_class=HTMLResponse)
async def delete_world(request: Request, world_id: int):
    uni_service = UniverseService()
    uni_service.delete_universe(world_id)
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)


@router.post("/reset-all-explored", response_class=HTMLResponse)
async def reset_all_explored(request: Request):
    uni_service = UniverseService()
    count = uni_service.reset_all_explored()
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)
