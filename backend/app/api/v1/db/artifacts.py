from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from typing import Sequence, Any
from sqlmodel import Session, select

from app.core.dependencies import get_main_session
from app.db.schema import Artifact
from app.services.artifact_service import ArtifactService
from app.repositories.artifact import ArtifactRepository
from app.core.templates import templates

router = APIRouter(tags=["artifacts"])

@router.get("/", response_model=list[dict[str, Any]])
def list_artifacts_json(
    limit: int = 100, 
    offset: int = 0, 
    session: Session = Depends(get_main_session)
):
    repo = ArtifactRepository(session)
    artifacts = repo.get_all(limit=limit, offset=offset)
    return [
        {
            "id": a.id,
            "name": a.name,
            "type": a.type,
            "universe_id": a.universe_id,
            "description": a.description,
        }
        for a in artifacts
    ]

@router.get("/list", response_class=HTMLResponse)
def list_artifacts(
    request: Request,
    universe_id: int | None = Query(default=None),
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_main_session)
):
    service = ArtifactService(session)
    artifacts = service.list_artifacts(universe_id=universe_id, limit=limit, offset=offset)
    template = templates.env.get_template("components/artifact_list.html")
    return HTMLResponse(content=template.render(
        request=request, artifacts=artifacts
    ))

@router.get("/search", response_class=HTMLResponse)
def search_artifacts(
    request: Request,
    universe_id: int = Query(default=None),
    q: str = Query(...),
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_main_session)
):
    service = ArtifactService(session)
    artifacts = service.list_artifacts(universe_id=universe_id, search_query=q, limit=limit, offset=offset)
    template = templates.env.get_template("components/artifact_list.html")
    return HTMLResponse(content=template.render(
        request=request, artifacts=artifacts
    ))

@router.get("/{artifact_id}", response_class=HTMLResponse)
def get_artifact(
    request: Request,
    artifact_id: int,
    session: Session = Depends(get_main_session)
):
    service = ArtifactService(session)
    art = service.get_artifact_details(artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found")
    template = templates.env.get_template("components/artifact_detail.html")
    return HTMLResponse(content=template.render(
        request=request, art=art
    ))
