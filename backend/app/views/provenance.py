from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.core.dependencies import get_main_session, get_unconfirmed_session
from app.core.templates import templates
from app.db.schema import Artifact, Evidence
from app.db.unconfirmed_schema import NotebookEntry

router = APIRouter(tags=["provenance_views"])


@router.get("/unconfirmed/{claim_id}", response_class=HTMLResponse)
async def unconfirmed_claim_provenance(
    request: Request,
    claim_id: int,
    session: Annotated[Session, Depends(get_unconfirmed_session)],
):
    entry = session.get(NotebookEntry, claim_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Notebook entry not found")

    # Note: NotebookEntry doesn't have a direct artifact_id like Claim did.
    # For now, we return None for artifact.
    artifact = None

    template = templates.env.get_template("pages/provenance.html")
    return HTMLResponse(content=template.render(
        request=request,
        claim=entry,
        subject=None,
        predicate=None,
        evidence_chunk=None,
        evidence=None,
        artifact=artifact,
        is_unconfirmed=True
    ))

@router.get("/claim/{claim_id}", response_class=HTMLResponse)
async def claim_provenance(
    request: Request,
    claim_id: int,
    main_session: Annotated[Session, Depends(get_main_session)],
):
    artifact = main_session.get(Artifact, claim_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Resolve Evidence
    evidence_chunk = None
    evidence = None
    if artifact.evidence_id:
        # We need a way to get the chunk. For now, we'll use a simplified approach.
        from app.db.schema import EvidenceChunk
        evidence_chunk = main_session.get(EvidenceChunk, artifact.evidence_id)
        if evidence_chunk:
            evidence = main_session.get(Evidence, evidence_chunk.evidence_id)

    # Resolve Provenance Artifact
    prov_artifact = None
    # In the new system, provenance is often in the payload_json or we can look it up.

    template = templates.env.get_template("pages/provenance.html")
    return HTMLResponse(content=template.render(
        request=request,
        claim=artifact,
        subject=None,
        predicate=None,
        object_entity=None,
        evidence_chunk=evidence_chunk,
        evidence=evidence,
        artifact=prov_artifact,
    ))


