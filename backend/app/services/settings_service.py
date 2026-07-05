from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.settings_session import settings_engine, get_settings_session
from app.db.schema import Setting, ProviderConfig, ProviderKey, AgentRouteFallback
from app.repositories.settings import SettingsRepository

class SettingsService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session

    def get_setting(self, key: str) -> Optional[Setting]:
        with Session(settings_engine) if not self.session else self.session as session:
            return SettingsRepository(session).get_setting(key)

    def get_all_settings(self) -> Dict[str, Any]:
        with Session(settings_engine) if not self.session else self.session as session:
            repo = SettingsRepository(session)
            settings = repo.get_all_settings()
            providers = repo.get_providers()
            routes = repo.get_agent_routes()
            
            provider_details = []
            for p in providers:
                keys = repo.get_keys_for_provider(p.id)
                provider_details.append({
                    "id": p.id,
                    "name": p.name,
                    "provider_type": p.provider_type,
                    "base_url": p.base_url,
                    "models": p.models,
                    "keys": [{"id": k.id, "api_key": k.api_key, "priority": k.priority} for k in keys]
                })
            
            return {
                "general_settings": {s.key: s.value for s in settings},
                "providers": provider_details,
                "agent_routes": [
                    {
                        "id": r.id,
                        "task_type": r.task_type,
                        "provider_id": r.provider_id,
                        "models": r.models,
                        "priority": r.priority,
                    } for r in routes
                ],
            }

    def update_general_setting(self, key: str, value: Optional[str]) -> Setting:
        with Session(settings_engine) if not self.session else self.session as session:
            return SettingsRepository(session).upsert_setting(key, value)

    def upsert_provider(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with Session(settings_engine) if not self.session else self.session as session:
            repo = SettingsRepository(session)
            provider_id = payload.get("id")
            name = payload.get("name")
            
            provider = None
            if provider_id:
                provider = repo.get_provider_by_id(provider_id)
            elif name:
                provider = repo.get_provider_by_name(name)
                
            if not provider:
                from app.db.schema import ProviderConfig
                provider = ProviderConfig(name=name)
            
            for field in ["provider_type", "base_url", "models"]:
                if field in payload:
                    setattr(provider, field, payload[field])
            
            updated = repo.upsert_provider(provider)
            return {"status": "success", "provider": {"id": updated.id, "name": updated.name}}

    def upsert_provider_key(self, provider_id: int, api_key: str, priority: int = 0, key_id: Optional[int] = None) -> int:
        with Session(settings_engine) if not self.session else self.session as session:
            repo = SettingsRepository(session)
            from app.db.schema import ProviderKey
            key = repo.session.get(ProviderKey, key_id) if key_id else None
            if not key:
                key = ProviderKey(provider_id=provider_id)
            key.api_key = api_key
            key.priority = priority
            updated = repo.upsert_key(key)
            return updated.id

    def delete_provider_key(self, key_id: int):
        with Session(settings_engine) if not self.session else self.session as session:
            SettingsRepository(session).delete_key(key_id)

    def delete_provider(self, provider_id: int):
        with Session(settings_engine) if not self.session else self.session as session:
            SettingsRepository(session).delete_provider(provider_id)

    def upsert_agent_route(self, task_type: str, provider_id: Optional[int], models: Optional[str], priority: int = 0, route_id: Optional[int] = None) -> None:
        with Session(settings_engine) if not self.session else self.session as session:
            repo = SettingsRepository(session)
            if provider_id:
                if not repo.get_provider_by_id(provider_id):
                    raise ValueError("Invalid provider_id")
            
            from app.db.schema import AgentRouteFallback
            route = repo.get_route_by_id(route_id) if route_id else None
            if not route:
                route = AgentRouteFallback(task_type=task_type)
            
            route.provider_id = provider_id
            route.models = models
            route.priority = priority
            repo.upsert_route(route)

    def delete_agent_route(self, route_id: int):
        with Session(settings_engine) if not self.session else self.session as session:
            SettingsRepository(session).delete_route(route_id)

    def get_agent_routes(self) -> List[Dict[str, Any]]:
        with Session(settings_engine) if not self.session else self.session as session:
            routes = SettingsRepository(session).get_agent_routes()
            return [
                {
                    "id": r.id,
                    "task_type": r.task_type,
                    "provider_id": r.provider_id,
                    "models": r.models,
                    "priority": r.priority,
                } for r in routes
            ]

    def get_providers(self) -> List[Dict[str, Any]]:
        with Session(settings_engine) if not self.session else self.session as session:
            repo = SettingsRepository(session)
            providers = repo.get_providers()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "provider_type": p.provider_type,
                    "base_url": p.base_url,
                    "models": p.models,
                    "keys": [
                        {"id": k.id, "api_key": k.api_key, "priority": k.priority}
                        for k in repo.get_keys_for_provider(p.id)
                    ]
                }
                for p in providers
            ]

    def reset_candidate_health(self):
        with Session(settings_engine) if not self.session else self.session as session:
            SettingsRepository(session).reset_candidate_health()

