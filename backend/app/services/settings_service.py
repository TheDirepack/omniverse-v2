from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import Setting, ProviderConfig, ProviderKey, AgentRouteFallback
from app.repositories.settings import SettingsRepository

class SettingsService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or Session(engine)
        self.repo = SettingsRepository(self.session)

    def get_all_settings(self) -> Dict[str, Any]:
        settings = self.repo.get_all_settings()
        providers = self.repo.get_providers()
        routes = self.repo.get_agent_routes()
        
        provider_details = []
        for p in providers:
            keys = self.repo.get_keys_for_provider(p.id)
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
        return self.repo.upsert_setting(key, value)

    def upsert_provider(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider_id = payload.get("id")
        name = payload.get("name")
        
        provider = None
        if provider_id:
            provider = self.repo.get_provider_by_id(provider_id)
        elif name:
            provider = self.repo.get_provider_by_name(name)
            
        if not provider:
            from app.db.schema import ProviderConfig
            provider = ProviderConfig(name=name)
        
        # Update fields
        for field in ["provider_type", "base_url", "models"]:
            if field in payload:
                setattr(provider, field, payload[field])
        
        updated = self.repo.upsert_provider(provider)
        return {"status": "success", "provider": {"id": updated.id, "name": updated.name}}

    def upsert_provider_key(self, provider_id: int, api_key: str, priority: int = 0, key_id: Optional[int] = None) -> int:
        from app.db.schema import ProviderKey
        key = self.repo.session.get(ProviderKey, key_id) if key_id else None
        if not key:
            key = ProviderKey(provider_id=provider_id)
        key.api_key = api_key
        key.priority = priority
        updated = self.repo.upsert_key(key)
        return updated.id

    def delete_provider_key(self, key_id: int):
        self.repo.delete_key(key_id)

    def delete_provider(self, provider_id: int):
        self.repo.delete_provider(provider_id)

    def upsert_agent_route(self, task_type: str, provider_id: Optional[int], models: Optional[str], priority: int = 0, route_id: Optional[int] = None) -> None:
        from app.db.schema import AgentRouteFallback
        route = self.repo.get_route_by_id(route_id) if route_id else None
        if not route:
            route = AgentRouteFallback(task_type=task_type)
        
        route.provider_id = provider_id
        route.models = models
        route.priority = priority
        self.repo.upsert_route(route)

    def delete_agent_route(self, route_id: int):
        self.repo.delete_route(route_id)

    def get_agent_routes(self) -> List[Dict[str, Any]]:
        routes = self.repo.get_agent_routes()
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
        providers = self.repo.get_providers()
        return [
            {
                "id": p.id,
                "name": p.name,
                "provider_type": p.provider_type,
                "base_url": p.base_url,
                "models": p.models,
                "keys": [
                    {"id": k.id, "api_key": k.api_key, "priority": k.priority}
                    for k in self.repo.get_keys_for_provider(p.id)
                ]
            }
            for p in providers
        ]

    def reset_candidate_health(self):
        self.repo.reset_candidate_health()
