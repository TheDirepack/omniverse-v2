from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.templates import templates
from app.db.schema import Claim
from app.db.session import engine
from app.repositories.acquisition_cache import AcquisitionCacheRepository

router = APIRouter(tags=["provenance_views"])


def _get_trace(target_type: str, target_id: int) -> list[dict]:
    repo = AcquisitionCacheRepository()
    try:
        edges = repo.get_provenance_for_claim(target_type, target_id)
        trace = []
        seen = set()
        for edge in edges:
            if edge.source_artifact_id in seen:
                continue
            seen.add(edge.source_artifact_id)
            artifact = repo.get_artifact(edge.source_artifact_id)
            trace.append({
                "edge": edge,
                "artifact": artifact,
            })
        return trace
    finally:
        repo.close()


@router.get("/claim/{claim_id}", response_class=HTMLResponse)
async def provenance_for_claim(request: Request, claim_id: int):
    with Session(engine) as session:
        claim = session.get(Claim, claim_id)
        if not claim:
            return HTMLResponse(
                "<p class='text-red-500'>Claim not found.</p>", status_code=404
            )
    trace = _get_trace("main_claim", claim_id)
    template = templates.env.get_template("fragments/provenance_trace.html")
    return HTMLResponse(
        content=template.render(
            request=request,
            trace=trace,
            claim_id=claim_id,
            show_full=True,
        )
    )


@router.get("/artifact/{artifact_id}", response_class=HTMLResponse)
async def provenance_for_artifact(request: Request, artifact_id: int):
    repo = AcquisitionCacheRepository()
    try:
        artifact = repo.get_artifact(artifact_id)
        if not artifact:
            return HTMLResponse(
                "<p class='text-red-500'>Artifact not found.</p>", status_code=404
            )
        usages = repo.get_usages(artifact_id)
        template = templates.env.get_template("fragments/provenance_trace.html")
        return HTMLResponse(
            content=template.render(
                request=request,
                artifact=artifact,
                usages=usages,
                show_full=False,
            )
        )
    finally:
        repo.close()
