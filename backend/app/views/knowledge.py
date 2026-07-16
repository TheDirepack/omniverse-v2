from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, func, select

from app.core.dependencies import get_main_session, get_universe_service
from app.core.templates import templates
from app.core.utils import get_active_world_id
from app.db.schema import Artifact, ArtifactRelation
from app.services.universe_service import UniverseService

router = APIRouter(tags=["knowledge_views"])

@router.get("/", response_class=HTMLResponse)
async def knowledge_page(request: Request, uni_service: Annotated[UniverseService, Depends(get_universe_service)]):
    active_world_uuid = get_active_world_id(request.cookies.get("active_world_id"))
    current_world = None
    if active_world_uuid:
        current_world = uni_service.get_universe_by_uuid(active_world_uuid)

    worlds = uni_service.get_all_universes(limit=5000)

    template = templates.env.get_template("pages/knowledge.html")
    return HTMLResponse(content=template.render(
        request=request, current_world=current_world, worlds=worlds,
        active_world_id=active_world_uuid, current_path=str(request.url.path),
    ))

@router.get("/worlds", response_class=HTMLResponse)
async def list_worlds(
    request: Request,
    session: Annotated[Session, Depends(get_main_session)],
    uni_service: Annotated[UniverseService, Depends(get_universe_service)],
    q: str = Query(default=""),
    has_artifacts: bool = Query(default=False),
    limit: int = 5000,
    offset: int = 0,
):
    worlds = uni_service.get_all_universes(limit=limit, offset=offset)

    if q:
        worlds = [w for w in worlds if q.lower() in (w.name or "").lower()]

    world_ids = [w.id for w in worlds]
    if not world_ids:
        return HTMLResponse(content=templates.env.get_template("components/world_list.html").render(request=request, worlds=[], selected_world_id=None))

    counts_query = select(Artifact.universe_id, func.count(Artifact.id)).where(
        Artifact.universe_id.in_(world_ids)
    ).group_by(Artifact.universe_id)
    counts = session.exec(counts_query).all()
    artifact_counts = dict(counts)

    result = []
    for w in worlds:
        count = artifact_counts.get(w.id, 0)
        if has_artifacts and count == 0:
            continue
        result.append({
            "id": w.id,
            "name": w.name,
            "franchise": getattr(w, "franchise", None),
            "artifact_count": count,
        })

    template = templates.env.get_template("components/world_list.html")
    return HTMLResponse(content=template.render(request=request, worlds=result, selected_world_id=None))

@router.get("/worlds/{world_id}", response_class=HTMLResponse)
async def world_detail(
    request: Request,
    world_id: int,
    session: Annotated[Session, Depends(get_main_session)],
    uni_service: Annotated[UniverseService, Depends(get_universe_service)],
):
    world = uni_service.get_universe_by_id(world_id)
    if not world:
        return HTMLResponse("World not found", status_code=404)

    entities = session.exec(
        select(Artifact).where(
            Artifact.universe_id == world_id, Artifact.type == "entity"
        )
    ).all()

    claims = session.exec(
        select(ArtifactRelation).where(ArtifactRelation.universe_id == world_id)
    ).all()

    artifact_ids = set()
    for c in claims:
        artifact_ids.add(c.from_artifact_id)
        artifact_ids.add(c.to_artifact_id)

    artifacts_map = {}
    if artifact_ids:
        arts = session.exec(select(Artifact).where(Artifact.id.in_(artifact_ids))).all()
        artifacts_map = {a.id: {"name": a.name, "type": a.type} for a in arts}

    template = templates.env.get_template("components/world_detail.html")
    return HTMLResponse(content=template.render(
        request=request, world=world, entities=entities, claims=claims,
        artifact_names=artifacts_map,
    ))

@router.get("/worlds/{world_id}/children", response_class=HTMLResponse)
async def world_children(
    request: Request,
    world_id: int,
    uni_service: Annotated[UniverseService, Depends(get_universe_service)],
):
    children = uni_service.get_universe_relations(world_id, direction="out")
    template = templates.env.get_template("components/world_row.html")
    return HTMLResponse(content=template.render(request=request, worlds=children))

@router.get("/entities/{entity_id}", response_class=HTMLResponse)
async def entity_detail(
    request: Request,
    entity_id: int,
    session: Annotated[Session, Depends(get_main_session)],
):
    entity = session.get(Artifact, entity_id)
    if not entity:
        return HTMLResponse("Entity not found", status_code=404)

    claims = session.exec(
        select(ArtifactRelation).where(ArtifactRelation.from_artifact_id == entity_id)
    ).all()

    template = templates.env.get_template("components/entity_detail.html")
    return HTMLResponse(
        content=template.render(request=request, entity=entity, claims=claims)
    )
