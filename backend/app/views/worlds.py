import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Form, Query, Request
from fastapi.responses import HTMLResponse

from app.core.templates import templates
from app.services.universe_service import UniverseService

router = APIRouter(tags=["worlds_views"])

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

@router.get("/", response_class=HTMLResponse)
async def worlds_page(request: Request):
    template = templates.env.get_template("pages/worlds.html")
    return HTMLResponse(content=template.render(request=request))

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

@router.post("/batch-research", response_class=HTMLResponse)
async def batch_research(
    request: Request,
    background_tasks: BackgroundTasks,
    world_names: str = Form(...),
):
    import uuid

    from app.api.routers.runs import run_pipeline_in_background
    names = [w.strip() for w in world_names.split(",") if w.strip()]
    for name in names:
        run_id = str(uuid.uuid4())
        background_tasks.add_task(run_pipeline_in_background, run_id, [name])
    uni_service = UniverseService()
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds, batch_started=len(names))


@router.post("/{world_id}/toggle-explored", response_class=HTMLResponse)
async def toggle_explored(request: Request, world_id: int):

    uni_service = UniverseService()
    uni_service.reset_explored(world_id)
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)

@router.post("/{world_id}/delete", response_class=HTMLResponse)
async def delete_world(request: Request, world_id: int):

    uni_service = UniverseService()
    uni_service.delete_universe(world_id)
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)

@router.post("/reset-all-explored", response_class=HTMLResponse)
async def reset_all_explored(request: Request):
    uni_service = UniverseService()
    uni_service.reset_all_explored()
    worlds = uni_service.get_all_universes(limit=5000)
    return _render_worlds(request, worlds)

@router.post("/set-active-world", response_class=HTMLResponse)
async def set_active_world(_request: Request, world_id: str = Form(...)):
    response = HTMLResponse(content="OK")
    response.set_cookie(key="active_world_id", value=world_id)
    return response



@router.get("/import", response_class=HTMLResponse)
async def worlds_import_fragment(request: Request, q: str = Query(default="")):
    json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
    entries = []
    if json_path.exists():
        def _read_json():
            with json_path.open() as f:
                return json.load(f)
        all_entries = await asyncio.to_thread(_read_json)

        service = UniverseService()
        existing = service.get_all_universes(limit=5000)
        existing_slugs = {w.slug for w in existing if w.slug}
        existing_names = {w.name for w in existing}

        if q:
            q_lower = q.lower()
            entries = [
                e
                for e in all_entries
                if ((q_lower in (e.get("name") or "").lower()
                        or q_lower in (e.get("franchise") or "").lower()
                        or q_lower in (e.get("continuity") or "").lower()
                        or q_lower in (e.get("era") or "").lower())
                        and e.get("id") not in existing_slugs
                        and e.get("name") not in existing_names)

            ]
        else:
            entries = [
                e for e in all_entries[:50]
                if e.get("id") not in existing_slugs
                and e.get("name") not in existing_names
            ]

    template = templates.env.get_template("fragments/world_import_list.html")
    return HTMLResponse(content=template.render(request=request, entries=entries, q=q))


@router.post("/import/{world_id}", response_class=HTMLResponse)
async def worlds_import_action(request: Request, world_id: str):
    service = UniverseService()
    world = service.import_from_registry(world_id)
    json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
    entries = []
    if json_path.exists():
        def _read_json():
            with json_path.open() as f:
                return json.load(f)
        entries = await asyncio.to_thread(_read_json)
    template = templates.env.get_template("fragments/world_import_list.html")
    return HTMLResponse(
        content=template.render(
            request=request, entries=entries[:50],
            imported=world.name if world else None
        )
    )


@router.post("/import-all", response_class=HTMLResponse)
async def worlds_import_all_action(request: Request):
    service = UniverseService()
    imported, skipped = service.import_all_from_registry()
    json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
    entries = []
    if json_path.exists():
        def _read_json():
            with json_path.open() as f:
                return json.load(f)
        entries = await asyncio.to_thread(_read_json)
    template = templates.env.get_template("fragments/world_import_list.html")
    return HTMLResponse(
        content=template.render(
            request=request, entries=entries[:50],
            imported=f"{imported} worlds (skipped {skipped})"
        )
    )


@router.get("/create", response_class=HTMLResponse)
async def worlds_create_fragment(request: Request):
    service = UniverseService()
    parents = service.get_all_universes(limit=200)
    template = templates.env.get_template("fragments/world_create_form.html")
    return HTMLResponse(content=template.render(request=request, parents=parents))


@router.post("/create", response_class=HTMLResponse)
async def worlds_create_action(
    request: Request,
    name: str = Form(...),
    franchise: str = Form(default=""),
    category: str = Form(default=""),
    continuity: str = Form(default=""),
    era: str = Form(default=""),
    parent_id: int = Form(default=None),
):
    service = UniverseService()
    existing = service.get_universe(name)
    if existing:
        from fastapi.responses import HTMLResponse as Resp
        return Resp(
            content=f'<p class="text-red-500">World "{name}" already exists.</p>',
            status_code=409,
        )
    service.create_universe(
        name=name,
        franchise=franchise or None,
        category=category or None,
        continuity=continuity or None,
        era=era or None,
        parent_id=parent_id or None,
    )
    parents = service.get_all_universes(limit=200)
    template = templates.env.get_template("fragments/world_create_form.html")
    return HTMLResponse(
        content=template.render(request=request, parents=parents, created=name)
    )


@router.get("/graph", response_class=HTMLResponse)
async def worlds_graph_fragment(request: Request):
    service = UniverseService()
    worlds = service.get_all_universes(limit=500)
    template = templates.env.get_template("fragments/world_hierarchy.html")
    return HTMLResponse(content=template.render(request=request, worlds=worlds))


@router.get("/{uuid}/neighborhood", response_class=HTMLResponse)
async def world_neighborhood(request: Request, uuid: str):
    service = UniverseService()
    world = service.get_universe_by_uuid(uuid)
    if not world:
        return HTMLResponse(
            "<p class='text-red-500'>World not found.</p>", status_code=404
        )
    related = service.get_related_universes(world.id) if world.id else []
    template = templates.env.get_template("fragments/world_neighborhood.html")
    return HTMLResponse(
        content=template.render(request=request, world=world, related=related)
    )


# Remove snapshots endpoints - moved to settings.py


# Remove snapshots endpoints - moved to settings.py



# Remove snapshots endpoints - moved to settings.py



# Remove snapshots endpoints - moved to settings.py

