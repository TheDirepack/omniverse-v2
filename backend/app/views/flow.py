from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select, and_

from app.core.templates import templates
from app.core.dependencies import get_main_session, get_unconfirmed_session
from app.db.session import engine as main_engine
from app.db.unconfirmed_session import unconfirmed_engine
from app.db.schema import Claim, Entity, Predicate, Evidence, EvidenceChunk, InferredClaim, InferredClaimPath
from app.db.unconfirmed_schema import UnconfirmedClaim

router = APIRouter(tags=["flow_views"])

@router.get("/", response_class=HTMLResponse)
async def flow_page(request: Request):
    template = templates.env.get_template("pages/flow.html")
    return HTMLResponse(content=template.render(request=request))

@router.get("/trace", response_class=HTMLResponse)
async def trace_claim_query(
    request: Request, 
    claim_id: int, 
    main_session: Session = Depends(get_main_session),
    unconfirmed_session: Session = Depends(get_unconfirmed_session)
):
    return await trace_claim(request, claim_id, main_session, unconfirmed_session)

@router.get("/{claim_id}", response_class=HTMLResponse)
async def trace_claim(
    request: Request, 
    claim_id: int, 
    main_session: Session = Depends(get_main_session),
    unconfirmed_session: Session = Depends(get_unconfirmed_session)
):
    claim = main_session.get(Claim, claim_id)
    if not claim:
        return HTMLResponse("Claim not found", status_code=404)
    
    # 1. Find Source Evidence
    source_evidence = None
    if claim.evidence_chunk_id:
        chunk = main_session.get(EvidenceChunk, claim.evidence_chunk_id)
        if chunk:
            source_evidence = main_session.get(Evidence, chunk.evidence_id)
    
    # 2. Find matching Unconfirmed Claim (heuristic)
    # Try to match subject, predicate, and object_literal
    subject = main_session.get(Entity, claim.subject_id)
    predicate = main_session.get(Predicate, claim.predicate_id)
    
    unconfirmed_match = None
    if subject and predicate:
        # Use the literal object if available, else try to find entity name
        obj_val = claim.object_literal
        if not obj_val and claim.object_entity_id:
            obj_entity = main_session.get(Entity, claim.object_entity_id)
            if obj_entity:
                obj_val = obj_entity.name
        
        if obj_val:
            stmt = select(UnconfirmedClaim).where(
                and_(
                    UnconfirmedClaim.subject == subject.name,
                    UnconfirmedClaim.predicate == (predicate.canonical_name if predicate else claim.predicate),
                    UnconfirmedClaim.object_val == obj_val
                )
            )
            unconfirmed_match = unconfirmed_session.exec(stmt).first()

    # 3. Find Inferences derived from this claim
    paths = main_session.exec(
        select(InferredClaimPath).where(InferredClaimPath.claim_id == claim_id)
    ).all()
    
    inferences = []
    for path in paths:
        inf = main_session.get(InferredClaim, path.inferred_claim_id)
        if inf:
            inferences.append(inf)

    # Get object entity name if it's an entity
    object_name = None
    if claim.object_entity_id:
        obj_entity = main_session.get(Entity, claim.object_entity_id)
        if obj_entity:
            object_name = obj_entity.name

    template = templates.env.get_template("fragments/flow_step.html")
    return HTMLResponse(content=template.render(
        request=request, 
        claim=claim, 
        source=source_evidence, 
        unconfirmed=unconfirmed_match, 
        inferences=inferences,
        subject=subject,
        predicate=predicate,
        object_name=object_name
    ))
