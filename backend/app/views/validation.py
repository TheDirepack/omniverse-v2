from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from app.services.universe_service import UniverseService

from app.core.templates import templates
from app.core.dependencies import get_main_session, get_unconfirmed_session
from app.db.schema import Claim, Entity, Predicate, Universe
from app.db.unconfirmed_schema import UnconfirmedClaim, UnconfirmedUniverse

router = APIRouter(tags=["validation_views"])

@router.get("/", response_class=HTMLResponse)
async def validation_page(request: Request, session: Session = Depends(get_unconfirmed_session)):
    # 1. Pending claims
    claims = session.exec(select(UnconfirmedClaim)).all()

    # 2. Agent Status (from active runs)
    from app.core.runtime_state import get_active_runs
    active_runs = await get_active_runs()
    
    # 3. Recent Promotions (from main DB)
    from app.db.settings_session import settings_engine
    from app.db.schema import Claim
    from sqlmodel import Session as MainSession
    
    recent_promotions = []
    with MainSession(settings_engine) as main_session:
        promotions = main_session.exec(
            select(Claim).order_by(Claim.created_at.desc()).limit(10)
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
        candidates = uni_service.find_duplicates(w.name, all_worlds=all_worlds)
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
        claims=claims, 
        active_runs=active_runs, 
        recent_promotions=recent_promotions,
        recent_rejections=rejections,
        duplicates=duplicates
    ))

@router.post("/claim/{claim_id}/approve", response_class=HTMLResponse)
async def approve_claim(
    claim_id: int,
    session: Session = Depends(get_unconfirmed_session),
    main_session: Session = Depends(get_main_session)
):
    unconfirmed_claim = session.get(UnconfirmedClaim, claim_id)
    if not unconfirmed_claim:
        return Response(content="", status_code=404)

    # --- Promotion Logic ---
    try:
        # Find/Create Universe
        unconfirmed_universe = session.get(UnconfirmedUniverse, unconfirmed_claim.universe_id)
        if unconfirmed_universe:
            main_universe = main_session.exec(select(Universe).where(Universe.name == unconfirmed_universe.name)).first()
            if not main_universe:
                main_universe = Universe(name=unconfirmed_universe.name, slug=unconfirmed_universe.name.lower().replace(" ", "-"))
                main_session.add(main_universe)
                main_session.commit()
                main_session.refresh(main_universe)
        else:
            main_universe = None

        # Find/Create Predicate
        main_predicate = main_session.exec(select(Predicate).where(Predicate.canonical_name == unconfirmed_claim.predicate)).first()
        if not main_predicate:
            main_predicate = Predicate(canonical_name=unconfirmed_claim.predicate)
            main_session.add(main_predicate)
            main_session.commit()
            main_session.refresh(main_predicate)

        # Subject
        subject_entity = main_session.exec(select(Entity).where(Entity.name == unconfirmed_claim.subject)).first()
        if not subject_entity:
            u_id = main_universe.id if main_universe else None
            subject_entity = Entity(name=unconfirmed_claim.subject, entity_type="unknown", universe_id=u_id)
            main_session.add(subject_entity)
            main_session.commit()
            main_session.refresh(subject_entity)

        # Object Resolution
        object_entity_id = None
        object_literal = unconfirmed_claim.object_val
        
        # Try to find an existing entity for the object value in the main DB
        if object_literal:
            object_entity = main_session.exec(
                select(Entity).where(Entity.name == object_literal)
            ).first()
            if object_entity:
                object_entity_id = object_entity.id
                object_literal = None # Use entity ID instead of literal if found

        new_claim = Claim(
            subject_id=subject_entity.id,
            predicate_id=main_predicate.id,
            predicate=unconfirmed_claim.predicate,
            object_entity_id=object_entity_id,
            object_literal=object_literal,
            universe_scope=main_universe.id if main_universe else None,
            status="VERIFIED"
        )
        main_session.add(new_claim)
        main_session.commit()

        # 3. Remove from unconfirmed
        session.delete(unconfirmed_claim)
        session.commit()

        response = HTMLResponse(content="")
        response.headers["HX-Trigger"] = '{"showToast": {"value": "Claim approved and promoted", "type": "info"}}'
        return response

    except Exception as e:
        print(f"Error during claim approval: {e}")
        return HTMLResponse(content="", status_code=500)

@router.post("/claim/{claim_id}/reject", response_class=HTMLResponse)
async def reject_claim(claim_id: int, session: Session = Depends(get_unconfirmed_session)):
    unconfirmed_claim = session.get(UnconfirmedClaim, claim_id)
    if not unconfirmed_claim:
        return Response(content="", status_code=404)

    session.delete(unconfirmed_claim)
    session.commit()
    
    response = HTMLResponse(content="")
    response.headers["HX-Trigger"] = '{"showToast": {"value": "Claim rejected", "type": "info"}}'
    return response

@router.post("/entity/{entity_id}/merge", response_class=HTMLResponse)
async def merge_entity(entity_id: int):
    # Stubbed
    return ""
