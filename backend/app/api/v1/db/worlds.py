from fastapi import APIRouter, Depends, Query
from typing import Any
from sqlmodel import Session, select

from app.core.dependencies import get_main_session
from app.db.schema import Universe
from app.services.universe_service import UniverseService

router = APIRouter(tags=["worlds"])

@router.get("/", response_model=list[dict[str, Any]])
def list_universes_json(
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    universes = service.list_universes(limit=limit, offset=offset)
    return [
        {
            "id": u.id,
            "name": u.name,
            "slug": u.slug,
            "franchise": u.franchise,
            "category": u.category,
            "summary": u.summary,
            "is_explored": u.is_explored,
        }
        for u in universes
    ]

@router.post("/", response_model=dict[str, Any])
def create_universe(
    name: str,
    slug: str | None = None,
    franchise: str | None = None,
    category: str | None = None,
    continuity: str | None = None,
    era: str | None = None,
    summary: str | None = None,
    is_explored: bool = True,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    universe = service.create(
        name=name,
        slug=slug,
        franchise=franchise,
        category=category,
        continuity=continuity,
        era=era,
        summary=summary,
        is_explored=is_explored
    )
    return {
        "id": universe.id,
        "name": universe.name,
        "slug": universe.slug,
    }

@router.get("/{id}", response_model=Universe)
def get_universe(
    id: int | str,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    return service.get_universe_by_id(id)

@router.put("/{id}", response_model=Universe)
def update_universe(
    id: int | str,
    data: dict[str, Any],
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    universe = service.update_universe(id, data)
    return universe

@router.delete("/{id}")
def delete_universe(
    id: int | str,
    session: Session = Depends(get_main_session)
):
    service = UniverseService(session)
    service.delete_universe(id)
    return {"success": True}
