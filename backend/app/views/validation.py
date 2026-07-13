from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.dependencies import get_main_session, get_notebook_session
from app.core.templates import templates
from app.db.schema import Artifact
from app.db.notebook_schema import NotebookEntry
from app.services.universe_service import UniverseService

router = APIRouter(tags=["validation_views"])

@router.get("/", response_class=HTMLResponse)
async def validation_page(
    request: Request,
    session: Annotated[Session, Depends(get_notebook_session)],
):
    # 1. Pending entries from notebook
    entries = (
        session.exec(select(NotebookEntry).where(NotebookEntry.status == "OPEN"))
        .all()
    )

    # 2. Agent Status (from active runs)
    from app.core.runtime_state import get_active_runs
    active_runs = await get_active_runs()

    # 3. Recent Promotions (from main DB)
    from sqlmodel import Session as MainSession

    from app.db.settings_session import settings_engine

    recent_promotions = []
    with MainSession(settings_engine) as main_session:
        promotions = main_session.exec(
            select(Artifact).order_by(Artifact.created_at.desc()).limit(10)
        ).all()
        recent_promotions = promotions

    # 4. Recent Rejections (from logs)
    from app.services.execution_service import ExecutionService
    exec_service = ExecutionService()
    rejections = [
        log for log in exec_service.repo.get_recent_logs(limit=100)
        if log.status == "REJECTED"
    ][:10]

    # 5. Duplicate World Candidates
    uni_service = UniverseService()
    all_worlds = uni_service.get_all_universes()
    duplicates = []
    for w in all_worlds:
        candidates = uni_service.find_duplicates(w.name)
        # Filter out the world itself
        filtered_candidates = [c for c in candidates if c["id"] != w.id]
        if filtered_candidates:
            duplicates.append({
                "world": w,
                "candidates": filtered_candidates
            })

    template = templates.env.get_template("pages/validation.html")
    return HTMLResponse(content=template.render(
        request=request,
        claims=entries,
        active_runs=active_runs,
        recent_promotions=recent_promotions,
        recent_rejections=rejections,
        duplicates=duplicates
    ))

@router.post("/claim/{claim_id}/approve", response_class=HTMLResponse)
async def approve_claim(
    claim_id: int,
    session: Annotated[Session, Depends(get_notebook_session)],
    _main_session: Annotated[Session, Depends(get_main_session)],
):
    # This logic is now handled by the DB Architect agent.
    # For now, we just mark the notebook entry as RESOLVED.
    entry = session.get(NotebookEntry, claim_id)
    if not entry:
        return Response(content="", status_code=404)

    entry.status = "RESOLVED"
    session.add(entry)
    session.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = (
        '{"showToast": {"value": "Marked as resolved (ready for DB Architect)", "type": "info"}}'
    )
    return response

@router.post("/claim/{claim_id}/reject", response_class=HTMLResponse)
async def reject_claim(
    claim_id: int,
    session: Annotated[Session, Depends(get_notebook_session)],
):
    entry = session.get(NotebookEntry, claim_id)
    if not entry:
        return Response(content="", status_code=404)

    session.delete(entry)
    session.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = (
        '{"showToast": {"value": "Entry deleted", "type": "info"}}'
    )
    return response

@router.post("/entity/{entity_id}/merge", response_class=HTMLResponse)
async def merge_entity(_entity_id: int):
    # Stubbed
    return ""

