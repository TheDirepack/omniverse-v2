from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session
from app.db.session import engine
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/providers", tags=["providers"])

class ProviderPayload(BaseModel):
    id: Optional[int] = None
    name: str
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[str] = None

class ProviderKeyPayload(BaseModel):
    id: Optional[int] = None
    provider_id: int
    api_key: str
    priority: int = 0

@router.get("/")
def get_providers():
    service = SettingsService()
    return service.get_providers()

@router.post("/")
def upsert_provider(payload: ProviderPayload):
    service = SettingsService()
    return service.upsert_provider(payload.model_dump())

@router.get("/{provider_id}/models")
async def get_provider_models(provider_id: int):
    from app.core.provider_models import fetch_live_models
    from app.services.settings_service import SettingsService
    service = SettingsService()
    with Session(engine) as session:
        from app.repositories.settings import SettingsRepository
        repo = SettingsRepository(session)
        provider = repo.get_provider_by_id(provider_id)
        if not provider:
            return {"models": []}
        models = await fetch_live_models(provider)
        return {"models": models}

@router.post("/keys")
def upsert_provider_key(payload: ProviderKeyPayload):
    service = SettingsService()
    key_id = service.upsert_provider_key(
        provider_id=payload.provider_id,
        api_key=payload.api_key,
        priority=payload.priority,
        key_id=payload.id
    )
    return {"status": "success", "key_id": key_id}

@router.delete("/keys/{key_id}")
def delete_provider_key(key_id: int):
    service = SettingsService()
    service.delete_provider_key(key_id)
    return {"status": "success"}

@router.delete("/{provider_id}")
def delete_provider(provider_id: int):
    service = SettingsService()
    service.delete_provider(provider_id)
    return {"status": "success"}
