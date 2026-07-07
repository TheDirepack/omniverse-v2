from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.templates import templates
from app.core.dependencies import get_main_session, get_unconfirmed_session
from app.db.schema import Claim, Entity, Predicate, Evidence, EvidenceChunk
from app.db.unconfirmed_schema import AcquisitionArtifact, UnconfirmedClaim
from app.db.unconfirmed_session import unconfirmed_engine

router = APIRouter(tags=["provenance_views"])


@router.get("/unconfirmed/{claim_id}", response_class=HTMLResponse)
async def unconfirmed_claim_provenance(request: Request, claim_id: int, session: Session = Depends(get_unconfirmed_session)):
    claim = session.get(UnconfirmedClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Unconfirmed claim not found")
    
    artifact = None
    if claim.artifact_id:
        with Session(unconfirmed_engine) as unconfirmed_session:
            artifact = unconfirmed_session.get(AcquisitionArtifact, claim.artifact_id)
    
    template = templates.env.get_template("pages/provenance.html")
    return HTMLResponse(content=template.render(
        request=request,
        claim=claim,
        subject=None,
        predicate=None,
        evidence_chunk=None,
        evidence=None,
        artifact=artifact,
        is_unconfirmed=True
    ))

@router.get("/claim/{claim_id}", response_class=HTMLResponse)

async def claim_provenance(request: Request, claim_id: int, main_session: Session = Depends(get_main_session)):
    claim = main_session.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Resolve Subject and Predicate
    subject = main_session.get(Entity, claim.subject_id)
    predicate = main_session.get(Predicate, claim.predicate_id)
    
    # Resolve Evidence
    evidence_chunk = None
    evidence = None
    if claim.evidence_chunk_id:
        evidence_chunk = main_session.get(EvidenceChunk, claim.evidence_chunk_id)
        if evidence_chunk:
            evidence = main_session.get(Evidence, evidence_chunk.evidence_id)

    # Resolve Object
    object_entity = None
    if claim.object_entity_id:
        object_entity = main_session.get(Entity, claim.object_entity_id)

    # Resolve Provenance Artifact
    artifact = None
    if claim.artifact_id:
        with Session(unconfirmed_engine) as unconfirmed_session:
            artifact = unconfirmed_session.get(AcquisitionArtifact, claim.artifact_id)

    template = templates.env.get_template("pages/provenance.html")
    return HTMLResponse(content=template.render(
        request=request,
        claim=claim,
        subject=subject,
        predicate=predicate,
        object_entity=object_entity,
        evidence_chunk=evidence_chunk,
        evidence=evidence,
        artifact=artifact,
    ))

