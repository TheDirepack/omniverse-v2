from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import get_settings_service
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/providers", tags=["providers"])

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

@router.get("/")
def get_providers(service: SettingsService = Depends(get_settings_service)):
    return service.get_providers()

@router.post("/")
def upsert_provider(
    payload: ProviderPayload, service: SettingsService = Depends(get_settings_service)
):
    return service.upsert_provider(payload.model_dump())

@router.get("/{provider_id}/models")
async def get_provider_models(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
):
    from app.core.provider_models import fetch_live_models
    provider = service.get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    models = await fetch_live_models(provider)
    return {"models": models}

@router.post("/keys")
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

@router.delete("/keys/{key_id}")
def delete_provider_key(
    key_id: int, service: SettingsService = Depends(get_settings_service)
):
    if not service.delete_provider_key(key_id):
        raise HTTPException(status_code=404, detail="Provider key not found")
    return {"status": "success"}

@router.delete("/{provider_id}")
def delete_provider(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
):
    if not service.delete_provider(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"status": "success"}
