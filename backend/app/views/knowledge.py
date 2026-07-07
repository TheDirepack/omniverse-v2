from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.dependencies import get_main_session, get_universe_service
from app.core.templates import templates
from app.db.schema import Claim, Entity, Universe
from app.services.universe_service import UniverseService

router = APIRouter(tags=["knowledge_views"])

@router.get("/", response_class=HTMLResponse)
async def knowledge_page(request: Request):
    template = templates.env.get_template("pages/knowledge.html")
    return HTMLResponse(content=template.render(request=request))

@router.get("/worlds", response_class=HTMLResponse)
async def list_worlds(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    uni_service: UniverseService = Depends(get_universe_service)
):
    worlds = uni_service.get_all_universes(limit=limit, offset=offset)
    template = templates.env.get_template("fragments/world_row.html")
    return HTMLResponse(content=template.render(request=request, worlds=worlds))

@router.get("/worlds/{world_id}", response_class=HTMLResponse)
async def world_detail(
    request: Request,
    world_id: int,
    session: Session = Depends(get_main_session),
    uni_service: UniverseService = Depends(get_universe_service)
):
    world = uni_service.get_universe_by_id(world_id)
    if not world:
        return HTMLResponse("World not found", status_code=404)

    entities = session.exec(
        select(Entity).where(Entity.universe_id == world_id)
    ).all()

    claims = session.exec(
        select(Claim).where(Claim.universe_scope == world_id)
    ).all()

    template = templates.env.get_template("fragments/world_detail.html")
    return HTMLResponse(content=template.render(
        request=request, world=world, entities=entities, claims=claims
    ))

@router.get("/worlds/{world_id}/children", response_class=HTMLResponse)
async def world_children(
    request: Request,
    world_id: int,
    uni_service: UniverseService = Depends(get_universe_service)
):
    children = uni_service.get_universe_relations(world_id, direction="out")
    template = templates.env.get_template("fragments/world_row.html")
    return HTMLResponse(content=template.render(request=request, worlds=children))

@router.get("/entities/{entity_id}", response_class=HTMLResponse)
async def entity_detail(
    request: Request,
    entity_id: int,
    session: Session = Depends(get_main_session)
):
    entity = session.get(Entity, entity_id)
    if not entity:
        return HTMLResponse("Entity not found", status_code=404)

    claims = session.exec(select(Claim).where(Claim.subject_id == entity_id)).all()

    template = templates.env.get_template("fragments/entity_detail.html")
    return HTMLResponse(content=template.render(request=request, entity=entity, claims=claims))
