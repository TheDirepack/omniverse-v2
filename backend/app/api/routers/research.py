
from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.notebook_schema import NotebookClaim, NotebookUniverse
from app.db.notebook_session import notebook_engine
from app.services.theory_service import TheoryService
from app.services.tiering_service import TieringService
from app.services.universe_service import UniverseService

router = APIRouter(prefix="/research", tags=["research"])


class NotebookClaimResponse(BaseModel):
    subject: str
    predicate: str
    object_val: str
    universe_name: str
    context: str | None = None
    artifact_id: int | None = None
    reference: str | None = None
    wiki_source: str | None = None
    confidence: float | None = None


class ResearchWorldResult(BaseModel):
    id: int
    name: str
    summary: str | None = None
    is_explored: bool
    tier: int | None = None
    tier_justification: str | None = None
    theory: str | None = None
    theory_audit: str | None = None


class AnomalyResponse(BaseModel):
    world_id: int
    description: str
    detected_at: str


class ResearchResultsResponse(BaseModel):
    tier_system: str | None = None
    worlds: list[ResearchWorldResult]
    anomalies: list[AnomalyResponse]


class TheoryResponse(BaseModel):
    id: int
    universe_id: int
    theory: str
    auditor_feedback: str | None = None
    created_at: str


@router.get("/claims")
def get_claims(
    universe_ids: str | None = None,
    limit: int = 100,
    offset: int = 0,
    fields: list[str] | None = None,
):
    service = UniverseService()
    return service.get_claims(universe_ids, limit=limit, offset=offset, fields=fields)


@router.get("/claims/notebook", response_model=list[NotebookClaimResponse])
def get_notebook_claims(universe_ids: str | None = None):
    with Session(notebook_engine) as session:
        query = select(NotebookClaim, NotebookUniverse.name).join(
            NotebookUniverse
        )
        if universe_ids:
            names = [n.strip() for n in universe_ids.split(",") if n.strip()]
            query = query.where(NotebookUniverse.name.in_(names))

        results = session.exec(query).all()
        output = []
        for claim, name in results:
            claim_dict = claim.model_dump()
            claim_dict["universe_name"] = name
            output.append(NotebookClaimResponse(**claim_dict))

        return output


@router.get("/results", response_model=ResearchResultsResponse)
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
            ResearchWorldResult(
                id=uni.id,
                name=uni.name,
                summary=uni.summary,
                is_explored=uni.is_explored,
                tier=wt.tier_number if wt else None,
                tier_justification=wt.justification if wt else None,
                theory=th.theory_text if th else None,
                theory_audit=th.auditor_feedback if th else None,
            )
        )

    anomalies = tier_service.repo.get_all_anomalies()

    return ResearchResultsResponse(
        tier_system=tier_system.system_definition if tier_system else None,
        worlds=results,
        anomalies=[
            AnomalyResponse(
                world_id=a.universe_id,
                description=a.description,
                detected_at=str(a.detected_at),
            )
            for a in anomalies
        ],
    )


@router.get("/tiers")
def get_tiers():
    return get_results()


@router.get("/theories", response_model=list[TheoryResponse])
def get_theories():
    service = TheoryService()
    theories = service.repo.get_all_theories()
    return [
        TheoryResponse(
            id=t.id,
            universe_id=t.universe_id,
            theory=t.theory_text,
            auditor_feedback=t.auditor_feedback,
            created_at=str(t.created_at),
        )
        for t in theories
    ]
