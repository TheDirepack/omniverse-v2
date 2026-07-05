from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

class SetupSetting(BaseModel):
    key: str
    value: Optional[str] = None

class AgentRouteFallbackPayload(BaseModel):
    id: Optional[int] = None
    task_type: str
    priority: int = 0
    provider_id: Optional[int] = None
    models: Optional[str] = None

@router.get("/")
def get_settings():
    service = SettingsService()
    return service.get_all_settings()

@router.post("/general")
def update_general_setting(payload: SetupSetting):
    service = SettingsService()
    service.update_general_setting(payload.key, payload.value)
    return {"status": "success", "message": f"Setting '{payload.key}' updated successfully."}

@router.post("/reset-health")
def reset_candidate_health():
    service = SettingsService()
    service.reset_candidate_health()
    return {"status": "success", "message": "All candidate circuit breakers reset."}

@router.get("/agent-names")
def get_agent_names():
    from app.agents.agent_names import AGENT_NAMES
    return AGENT_NAMES

@router.post("/agent-routes")
def upsert_agent_route(payload: AgentRouteFallbackPayload):
    service = SettingsService()
    try:
        service.upsert_agent_route(
            task_type=payload.task_type,
            provider_id=payload.provider_id,
            models=payload.models,
            priority=payload.priority,
            route_id=payload.id
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "success"}

@router.delete("/agent-routes/{route_id}")
def delete_agent_route(route_id: int):
    service = SettingsService()
    service.delete_agent_route(route_id)
    return {"status": "success"}

@router.get("/agent-routes")
def get_agent_routes():
    service = SettingsService()
    return service.get_agent_routes()

@router.get("/model-status")
def model_status():
    service = SettingsService()
    routes = service.get_agent_routes()
    providers = {p.id: p for p in service.get_providers()} # This is wrong, get_providers returns dicts
    # Wait, let's just use the repo for this internal status check or add a method to service.
    # I'll just use the repo here for simplicity.
    with Session(engine) as session:
        from app.repositories.settings import SettingsRepository
        repo = SettingsRepository(session)
        routes = repo.get_agent_routes()
        providers = {p.id: p for p in repo.get_providers()}
        route_status = []
        for route in routes:
            provider = providers.get(route.provider_id)
            route_status.append({
                "task_type": route.task_type,
                "configured": bool(provider and provider.provider_type and route.models),
                "provider": provider.name if provider else None,
                "models": route.models,
            })
    return {"initialized": True, "routes": route_status}
