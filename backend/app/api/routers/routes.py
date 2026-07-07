from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_settings_service
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


class AgentRouteFallbackPayload(BaseModel):
    id: int | None = None
    task_type: str
    priority: int = 0
    provider_id: int | None = None
    models: str | None = None


@router.post("/agent-routes")
def upsert_agent_route(
    payload: AgentRouteFallbackPayload,
    service: SettingsService = Depends(get_settings_service),
):
    try:
        service.upsert_agent_route(
            task_type=payload.task_type,
            provider_id=payload.provider_id,
            models=payload.models,
            priority=payload.priority,
            route_id=payload.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "success"}


@router.delete("/agent-routes/{route_id}")
def delete_agent_route(
    route_id: int, service: SettingsService = Depends(get_settings_service)
):
    if not service.delete_agent_route(route_id):
        raise HTTPException(status_code=404, detail="Agent route not found")
    return {"status": "success"}


@router.get("/agent-routes")
def get_agent_routes(service: SettingsService = Depends(get_settings_service)):
    return service.get_agent_routes()
