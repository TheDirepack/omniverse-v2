from fastapi import APIRouter

from app.services.theory_service import TheoryService
from app.services.tiering_service import TieringService
from app.services.universe_service import UniverseService

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/claims")
def get_claims(
    universe_ids: str | None = None,
    limit: int = 100,
    offset: int = 0,
    fields: list[str] | None = None,
):
    service = UniverseService()
    return service.get_claims(universe_ids, limit=limit, offset=offset, fields=fields)


@router.get("/claims/unconfirmed")
def get_unconfirmed_claims(universe_ids: str | None = None):
    from sqlmodel import Session, select

    from app.db.unconfirmed_schema import UnconfirmedClaim, UnconfirmedUniverse
    from app.db.unconfirmed_session import unconfirmed_engine

    with Session(unconfirmed_engine) as session:
        query = select(UnconfirmedClaim, UnconfirmedUniverse.name).join(
            UnconfirmedUniverse
        )
        if universe_ids:
            names = [n.strip() for n in universe_ids.split(",") if n.strip()]
            query = query.where(UnconfirmedUniverse.name.in_(names))

        results = session.exec(query).all()
        output = []
        for claim, name in results:
            claim_dict = claim.model_dump()
            claim_dict["universe_name"] = name
            output.append(claim_dict)

        return output


@router.get("/results")
def get_results():
    uni_service = UniverseService()
    tier_service = TieringService()
    theory_service = TheoryService()

    universes = uni_service.get_all_universes()
    tier_system = tier_service.repo.get_latest_rubric()

    universe_ids = [u.id for u in universes]
    tiers_map = {}
    if universe_ids:
        tiers = tier_service.repo.get_world_tiers_by_universe_ids(universe_ids)
        for t in tiers:
            tiers_map[t.universe_id] = t

    theories_map = {}
    if universe_ids:
        theories = theory_service.repo.get_theories_by_universe_ids(universe_ids)
        for th in theories:
            theories_map[th.universe_id] = th

    results = []
    for uni in universes:
        wt = tiers_map.get(uni.id)
        th = theories_map.get(uni.id)
        results.append(
            {
                "id": uni.id,
                "name": uni.name,
                "summary": uni.summary,
                "is_explored": uni.is_explored,
                "tier": wt.tier_number if wt else None,
                "tier_justification": wt.justification if wt else None,
                "theory": th.theory_text if th else None,
                "theory_audit": th.auditor_feedback if th else None,
            }
        )

    anomalies = tier_service.repo.get_all_anomalies()

    return {
        "tier_system": tier_system.system_definition if tier_system else None,
        "worlds": results,
        "anomalies": [
            {
                "world_id": a.universe_id,
                "description": a.description,
                "detected_at": str(a.detected_at),
            }
            for a in anomalies
        ],
    }


@router.get("/tiers")
def get_tiers():
    return get_results()


@router.get("/theories")
def get_theories():
    service = TheoryService()
    theories = service.repo.get_all_theories()
    return [
        {
            "id": t.id,
            "universe_id": t.universe_id,
            "theory": t.theory_text,
            "auditor_feedback": t.auditor_feedback,
            "created_at": str(t.created_at),
        }
        for t in theories
    ]
