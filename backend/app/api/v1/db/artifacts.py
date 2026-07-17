from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.dependencies import get_main_session
from app.core.templates import templates
from app.repositories.artifact import ArtifactRepository
from app.services.artifact_service import ArtifactService

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

@router.post("/save")
async def save_artifact(
    data: dict[str, Any],
    session: Session = Depends(get_main_session)
):
    """Save a single artifact by type."""
    from app.services.artifact_service import ArtifactService

    service = ArtifactService(session)

    # Get existing artifact or create new
    existing = service.get_artifact_by_type_and_name(data.get("type"), data.get("name"))
    if existing:
        return {"status": "updated", "artifact_id": existing.id}

    # Create new artifact
    new_artifact = await service.create_artifact(
        content_type=data.get("type"),
        title=data.get("name"),
        description=data.get("description"),
        details=data.get("details"),
        raw_content=data.get("content"),
    )

    return {"status": "created", "artifact_id": new_artifact.id}
