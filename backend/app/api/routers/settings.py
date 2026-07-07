from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import Session

from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


class SetupSetting(BaseModel):
    key: str
    value: str | None = None


@router.get("/")
def get_settings():
    service = SettingsService()
    return service.get_all_settings()


@router.post("/general")
def update_general_setting(payload: SetupSetting):
    service = SettingsService()
    service.update_general_setting(payload.key, payload.value)
    return {
        "status": "success",
        "message": f"Setting '{payload.key}' updated successfully.",
    }


@router.post("/reset-health")
def reset_candidate_health():
    service = SettingsService()
    service.reset_candidate_health()
    return {"status": "success", "message": "All candidate circuit breakers reset."}


@router.get("/agent-names")
def get_agent_names():
    from app.agents.agent_names import AGENT_NAMES

    return AGENT_NAMES


@router.get("/model-status")
def model_status():
    with Session(settings_engine) as session:
        repo = SettingsRepository(session)
        routes = repo.get_agent_routes()
        providers = {p.id: p for p in repo.get_providers()}
        route_status = []
        for route in routes:
            provider = providers.get(route.provider_id)
            route_status.append(
                {
                    "task_type": route.task_type,
                    "configured": bool(
                        provider and provider.provider_type and route.models
                    ),
                    "provider": provider.name if provider else None,
                    "models": route.models,
                }
            )
    return {"initialized": True, "routes": route_status}
