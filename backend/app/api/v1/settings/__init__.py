from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_settings_service
from app.services.settings_service import SettingsService

# General settings sub-router
general_router = APIRouter(prefix="/general", tags=["general-settings"])

class SetupSetting(BaseModel):
    key: str
    value: str | None = None

@general_router.get("/")
def get_all_settings(service: SettingsService = Depends(get_settings_service)):
    return service.get_all_settings()

@general_router.post("/")
def update_general_setting(payload: SetupSetting, service: SettingsService = Depends(get_settings_service)):
    service.update_general_setting(payload.key, payload.value)
    return {
        "status": "success",
        "message": f"Setting '{payload.key}' updated successfully.",
    }

@general_router.post("/reset-health")
def reset_candidate_health(service: SettingsService = Depends(get_settings_service)):
    service.reset_candidate_health()
    return {"status": "success", "message": "All candidate circuit breakers reset."}

# Providers sub-router
providers_router = APIRouter(prefix="/providers", tags=["providers"])

class ProviderPayload(BaseModel):
    id: int | None = None
    name: str
    provider_type: str | None = None
    base_url: str | None = None
    models: str | None = None

class ProviderKeyPayload(BaseModel):
    id: int | None = None
    provider_id: int
    api_key: str
    priority: int = 0

@providers_router.get("/")
def get_providers(service: SettingsService = Depends(get_settings_service)):
    return service.get_providers()

@providers_router.post("/")
def upsert_provider(
    payload: ProviderPayload, service: SettingsService = Depends(get_settings_service)
):
    return service.upsert_provider(payload.model_dump())

@providers_router.get("/{provider_id}/models")
async def get_provider_models(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
):
    from app.core.provider_models import fetch_live_models
    provider = service.get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    models = await fetch_live_models(provider)
    return {"models": models}

@providers_router.post("/keys")
def upsert_provider_key(
    payload: ProviderKeyPayload, service: SettingsService = Depends(get_settings_service)
):
    key_id = service.upsert_provider_key(
        provider_id=payload.provider_id,
        api_key=payload.api_key,
        priority=payload.priority,
        key_id=payload.id
    )
    return {"status": "success", "key_id": key_id}

@providers_router.delete("/keys/{key_id}")
def delete_provider_key(
    key_id: int, service: SettingsService = Depends(get_settings_service)
):
    if not service.delete_provider_key(key_id):
        raise HTTPException(status_code=404, detail="Provider key not found")
    return {"status": "success"}

@providers_router.delete("/{provider_id}")
def delete_provider(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
):
    if not service.delete_provider(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"status": "success"}

# Routes sub-router
routes_router = APIRouter(prefix="/routes", tags=["agent-routes"])

class RouteStatusResponse(BaseModel):
    task_type: str
    configured: bool
    provider: str | None = None
    models: str | None = None

class ModelStatusResponse(BaseModel):
    initialized: bool
    routes: list[RouteStatusResponse]

class RoutePayload(BaseModel):
    task_type: str
    provider_id: int | None = None
    models: str | None = None
    priority: int = 0

@routes_router.get("/")
def get_agent_routes(service: SettingsService = Depends(get_settings_service)):
    return service.get_agent_routes()

@routes_router.post("/")
def create_route(payload: RoutePayload, service: SettingsService = Depends(get_settings_service)):
    try:
        service.upsert_agent_route(
            task_type=payload.task_type,
            provider_id=payload.provider_id,
            models=payload.models,
            priority=payload.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "status": "success",
        "message": f"Route '{payload.task_type}' created successfully.",
    }

@routes_router.get("/model-status")
def get_model_status(service: SettingsService = Depends(get_settings_service)):
    routes = service.get_agent_routes()
    route_statuses = [
        RouteStatusResponse(
            task_type=r["task_type"],
            configured=r["provider_id"] is not None,
            provider=r.get("provider_name"),
            models=r.get("models"),
        )
        for r in routes
    ]
    return ModelStatusResponse(initialized=True, routes=route_statuses)

@routes_router.get("/{task_type}")
def get_route_by_task_type(task_type: str, service: SettingsService = Depends(get_settings_service)):
    route = service.get_agent_route_by_task_type(task_type)
    if not route:
        raise HTTPException(status_code=404, detail=f"Route for task type '{task_type}' not found")
    return route

@routes_router.post("/{task_type}")
def configure_agent_route(payload: SetupSetting, task_type: str, service: SettingsService = Depends(get_settings_service)):
    service.configure_agent_route(task_type, payload.key, payload.value)
    return {
        "status": "success",
        "message": f"Route for '{task_type}/{payload.key}' configured successfully.",
    }

# Combine all routers
router = APIRouter()
router.include_router(general_router)
router.include_router(providers_router)
router.include_router(routes_router)
