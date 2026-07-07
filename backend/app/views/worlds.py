import json
from pathlib import Path

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse

from app.core.templates import templates
from app.services.universe_service import UniverseService

router = APIRouter(tags=["worlds_views"])


@router.get("/", response_class=HTMLResponse)
async def worlds_page(request: Request):
    template = templates.env.get_template("pages/worlds.html")
    return HTMLResponse(content=template.render(request=request))


@router.get("/import", response_class=HTMLResponse)
async def worlds_import_fragment(request: Request, q: str = Query(default="")):
    json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
    entries = []
    if json_path.exists():
        with open(json_path) as f:
            all_entries = json.load(f)

        service = UniverseService()
        existing = service.get_all_universes(limit=5000)
        existing_slugs = {w.slug for w in existing if w.slug}
        existing_names = {w.name for w in existing}

        if q:
            q_lower = q.lower()
            entries = [
                e
                for e in all_entries
                if (q_lower in e.get("name", "").lower()
                    or q_lower in e.get("franchise", "").lower())
                and e.get("id") not in existing_slugs
                and e.get("name") not in existing_names
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
        with open(json_path) as f:
            entries = json.load(f)
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
        with open(json_path) as f:
            entries = json.load(f)
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
        parent_id=parent_id if parent_id else None,
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
