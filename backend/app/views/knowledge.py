from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, func, select

from app.core.dependencies import get_main_session, get_universe_service
from app.core.templates import templates
from app.db.notebook_schema import NotebookUniverse
from app.db.schema import Artifact, ArtifactRelation
from app.services.theory_service import TheoryService
from app.services.universe_service import UniverseService

router = APIRouter(tags=["knowledge_views"])


@router.get("/", response_class=HTMLResponse)
async def knowledge_page(
    request: Request,
    world_id: str = Query(default=None),
    session: Annotated[Session, Depends(get_main_session)] = None,
):
    selected_world = None

    if world_id:
        uni_service = UniverseService(session)
        selected_world = uni_service.get_universe_by_uuid(world_id)
        if not selected_world and world_id.isdigit():
            selected_world = uni_service.get_universe_by_id(int(world_id))

    if selected_world:
        artifacts = session.exec(
            select(Artifact).where(Artifact.universe_id == selected_world.id)
        ).all()

        # Fetch notebook entries count
        notebook_count = 0
        try:
            from app.db.notebook_schema import NotebookEntry
            from app.db.notebook_session import notebook_engine
            nsession = Session(notebook_engine)
            notebook_count = len(nsession.exec(
                select(NotebookEntry).where(NotebookEntry.universe_uuid == selected_world.uuid)
            ).all())
            nsession.close()
        except Exception:
            pass

        # Fetch theory entry
        theory_entry = None
        try:
            theory_service = TheoryService()
            theories = theory_service.get_theories_by_universe_ids([selected_world.id], limit=1)
            theory_entry = theories[0] if theories else None
        except Exception:
            pass

        template = templates.env.get_template("pages/knowledge.html")
        return HTMLResponse(content=template.render(
            request=request,
            selected_world=selected_world,
            world=selected_world,
            artifacts=artifacts,
            notebook_count=notebook_count,
            theory_entry=theory_entry,
            current_path=str(request.url.path),
        ))
    # World list phase
    uni_service = UniverseService(session)
    worlds = uni_service.get_all_universes(limit=5000)
    template = templates.env.get_template("pages/knowledge.html")
    return HTMLResponse(content=template.render(
        request=request,
        worlds=worlds,
        selected_world=None,
        current_path=str(request.url.path),
    ))


@router.get("/worlds/list", response_class=HTMLResponse)
async def list_worlds_fragment(
    request: Request,
    uni_service: Annotated[UniverseService, Depends(get_universe_service)],
    session: Annotated[Session, Depends(get_main_session)],
    q: str = Query(default=""),
):
    worlds = uni_service.get_all_universes(limit=5000)
    if q:
        q_lower = q.lower()
        worlds = [w for w in worlds if q_lower in (w.name or "").lower()]

    world_ids = [w.id for w in worlds]
    if world_ids:
        counts_query = select(Artifact.universe_id, func.count(Artifact.id)).where(
            Artifact.universe_id.in_(world_ids)
        ).group_by(Artifact.universe_id)
        counts = session.exec(counts_query).all()
        artifact_counts = dict(counts)
    else:
        artifact_counts = {}

    result = []
    for w in worlds:
        result.append({
            "id": w.id,
            "uuid": w.uuid,
            "name": w.name,
            "is_explored": w.is_explored,
            "last_researched": getattr(w, "last_researched", None),
            "artifact_count": artifact_counts.get(w.id, 0),
        })

    template = templates.env.get_template("components/knowledge_world_list.html")
    return HTMLResponse(content=template.render(
        request=request, worlds=result
    ))


@router.get("/world/{world_id}/tab/{tab_name}", response_class=HTMLResponse)
async def world_tab_content(
    request: Request,
    world_id: int,
    tab_name: str,
    session: Annotated[Session, Depends(get_main_session)],
    uni_service: Annotated[UniverseService, Depends(get_universe_service)],
):
    world = uni_service.get_universe_by_id(world_id)
    if not world:
        return HTMLResponse("World not found", status_code=404)

    if tab_name == "overview":
        artifacts = session.exec(
            select(Artifact).where(Artifact.universe_id == world_id)
        ).all()
        notebook_count = 0
        try:
            from app.db.notebook_schema import NotebookEntry
            from app.db.notebook_session import notebook_engine
            nsession = Session(notebook_engine)
            notebook_count = len(nsession.exec(
                select(NotebookEntry).where(NotebookEntry.universe_uuid == world.uuid)
            ).all())
            nsession.close()
        except Exception:
            pass
        theory_entry = None
        try:
            theory_service = TheoryService()
            theories = theory_service.get_theories_by_universe_ids([world_id], limit=1)
            theory_entry = theories[0] if theories else None
        except Exception:
            pass

        # Relations/claims count
        claims_count = len(session.exec(
            select(ArtifactRelation).where(ArtifactRelation.universe_id == world_id)
        ).all())

        template = templates.env.get_template("components/knowledge_overview_tab.html")
        return HTMLResponse(content=template.render(
            request=request, world=world, artifacts=artifacts,
            notebook_count=notebook_count, theory_entry=theory_entry,
            claims_count=claims_count,
        ))

    if tab_name == "artifacts":
        artifacts = session.exec(
            select(Artifact).where(Artifact.universe_id == world_id)
        ).all()
        template = templates.env.get_template("components/artifact_list.html")
        return HTMLResponse(content=template.render(
            request=request, artifacts=artifacts
        ))

    if tab_name == "notebook":
        try:
            from app.db.notebook_schema import NotebookClaim, NotebookEntry
            from app.db.notebook_session import notebook_engine
            nsession = Session(notebook_engine)

            # Find notebook universe by uuid
            notebook_universe = nsession.exec(
                select(NotebookUniverse).where(
                    func.lower(NotebookUniverse.name) == func.lower(world.name)
                )
            ).first()

            entries = []
            claims = []
            if notebook_universe:
                entries = nsession.exec(
                    select(NotebookEntry).where(NotebookEntry.universe_uuid == world.uuid)
                ).all()
                claims = nsession.exec(
                    select(NotebookClaim).where(NotebookClaim.universe_id == notebook_universe.id)
                ).all()
            nsession.close()

            template = templates.env.get_template("components/knowledge_notebook_tab.html")
            return HTMLResponse(content=template.render(
                request=request, world=world, entries=entries, claims=claims
            ))
        except Exception as e:
            return HTMLResponse(f'<div class="p-6 text-red-500 text-sm">Error loading notebook: {e}</div>')

    elif tab_name == "theory":
        try:
            theory_service = TheoryService()
            theory = theory_service.get_theories_by_universe_ids([world_id], limit=1)
            template = templates.env.get_template("components/knowledge_theory_tab.html")
            return HTMLResponse(content=template.render(
                request=request, world=world,
                theory=theory[0] if theory else None
            ))
        except Exception as e:
            return HTMLResponse(f'<div class="p-6 text-red-500 text-sm">Error loading theory: {e}</div>')

    return HTMLResponse("Unknown tab", status_code=400)


@router.get("/notebook/entry/{entry_id}", response_class=HTMLResponse)
async def notebook_entry_detail(
    request: Request,
    entry_id: int,
):
    try:
        from app.db.notebook_schema import NotebookEntry
        from app.db.notebook_session import notebook_engine
        nsession = Session(notebook_engine)
        entry = nsession.get(NotebookEntry, entry_id)
        nsession.close()

        if not entry:
            return HTMLResponse("Entry not found", status_code=404)

        return HTMLResponse(content=f'''
<div class="p-6 space-y-4">
    <div class="flex items-center justify-between">
        <h3 class="text-sm font-bold text-gray-900 dark:text-gray-100">{entry.title}</h3>
        <button onclick="hideInspector()" class="text-gray-400 hover:text-gray-600 text-sm">✕</button>
    </div>
    <div>
        <div class="text-[10px] font-bold text-gray-400 uppercase mb-1">Kind</div>
        <span class="px-2 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 text-[10px] font-bold uppercase rounded-sm">{entry.kind}</span>
    </div>
    <div>
        <div class="text-[10px] font-bold text-gray-400 uppercase mb-1">Summary</div>
        <p class="text-sm text-gray-700 dark:text-gray-300">{entry.summary}</p>
    </div>
    {f'<div><div class="text-[10px] font-bold text-gray-400 uppercase mb-1">Details</div><p class="text-sm text-gray-700 dark:text-gray-300">{entry.details}</p></div>' if entry.details else ''}
    <div>
        <div class="text-[10px] font-bold text-gray-400 uppercase mb-1">Status</div>
        <span class="text-xs text-gray-600 dark:text-gray-400">{entry.status}</span>
    </div>
    <div class="text-[10px] text-gray-400">Created: {entry.created_at}</div>
</div>
''')
    except Exception as e:
        return HTMLResponse(f'<div class="p-6 text-red-500 text-sm">Error: {e}</div>')


