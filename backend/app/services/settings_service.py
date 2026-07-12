from typing import Any

from sqlmodel import Session

from app.db.operational_session import operational_engine
from app.db.schema import ProviderConfig, Setting
from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository

PROVIDER_PRESETS = {
    "openai": {
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": "",
    },
    "anthropic": {
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": "",
    },
    "google": {
        "provider_type": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": "",
    },
    "ollama": {
        "provider_type": "ollama",
        "base_url": "http://localhost:11434",
        "models": "",
    },
    "groq": {
        "provider_type": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": "",
    },
    "openrouter": {
        "provider_type": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": "",
    },
    "custom": {
        "provider_type": "custom",
        "base_url": "",
        "models": "",
    },
}


class SettingsService:
    def __init__(self, session: Session | None = None):
        self.session = session

    def get_setting(self, key: str) -> Setting | None:
        session = self.session or Session(settings_engine)
        try:
            return SettingsRepository(session).get_setting(key)
        finally:
            if not self.session:
                session.close()

    def get_provider_by_id(self, provider_id: int) -> ProviderConfig | None:
        session = self.session or Session(settings_engine)
        try:
            return SettingsRepository(session).get_provider_by_id(provider_id)
        finally:
            if not self.session:
                session.close()

    def get_all_settings(self) -> dict[str, Any]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            settings = repo.get_all_settings()
            providers = repo.get_providers()
            all_keys = repo.get_all_keys()
            routes = repo.get_agent_routes()

            keys_by_provider = {}
            for k in all_keys:
                keys_by_provider.setdefault(k.provider_id, []).append(k)

            provider_details = []
            for p in providers:
                assert p.id is not None
                keys = keys_by_provider.get(p.id, [])
                provider_details.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "provider_type": p.provider_type,
                        "base_url": p.base_url,
                        "models": p.models,
                        "keys": [
                            {"id": k.id, "api_key": k.api_key, "priority": k.priority}
                            for k in keys
                        ],
                    }
                )

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
                    }
                    for r in routes
                ],
            }
        finally:
            if not self.session:
                session.close()

    def update_general_setting(self, key: str, value: str | None) -> Setting:
        session = self.session or Session(settings_engine)
        try:
            res = SettingsRepository(session).upsert_setting(key, value)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def upsert_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        session = self.session or Session(settings_engine)
        try:
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

            for field in ["name", "provider_type", "base_url", "models"]:
                if field in payload:
                    setattr(provider, field, payload[field])

            updated = repo.upsert_provider(provider)
            session.commit()
            return {
                "status": "success",
                "provider": {"id": updated.id, "name": updated.name},
            }
        finally:
            if not self.session:
                session.close()

    def upsert_provider_key(
        self,
        provider_id: int,
        api_key: str,
        priority: int = 0,
        key_id: int | None = None,
    ) -> int:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            from app.db.schema import ProviderKey

            key = repo.session.get(ProviderKey, key_id) if key_id else None
            if not key:
                key = ProviderKey(provider_id=provider_id)
            key.api_key = api_key
            key.priority = priority
            updated = repo.upsert_key(key)
            session.commit()
            assert updated.id is not None
            return updated.id
        finally:
            if not self.session:
                session.close()

    def delete_provider_key(self, key_id: int) -> bool:
        session = self.session or Session(settings_engine)
        try:
            res = SettingsRepository(session).delete_key(key_id)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def delete_provider(self, provider_id: int) -> bool:
        session = self.session or Session(settings_engine)
        try:
            res = SettingsRepository(session).delete_provider(provider_id)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def upsert_agent_route(
        self,
        task_type: str,
        provider_id: int | None,
        models: str | None,
        priority: int = 0,
        route_id: int | None = None,
    ) -> None:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            if provider_id is not None and not repo.get_provider_by_id(provider_id):
                raise ValueError("Invalid provider_id")

            from app.db.schema import AgentRouteFallback

            route = repo.get_route_by_id(route_id) if route_id else None
            if not route:
                route = AgentRouteFallback(task_type=task_type)

            route.provider_id = provider_id
            route.models = models
            route.priority = priority
            repo.upsert_route(route)
            session.commit()
        finally:
            if not self.session:
                session.close()

    def delete_agent_route(self, route_id: int) -> bool:
        session = self.session or Session(settings_engine)
        try:
            res = SettingsRepository(session).delete_route(route_id)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def validate_settings(self) -> list[dict[str, str]]:
        """Validate the current settings configuration."""
        session = self.session or Session(settings_engine)
        try:
            all_settings = self.get_all_settings()
            issues = []

            # 1. Validate General Settings
            general = all_settings.get("general_settings", {})
            min_turns = general.get("MIN_RESEARCH_TURNS")
            if min_turns is None:
                issues.append({
                    "severity": "WARNING",
                    "message": "Setting 'MIN_RESEARCH_TURNS' is missing. Using default (6).",
                })
            elif not str(min_turns).isdigit():
                issues.append({
                    "severity": "ERROR",
                    "message": f"Setting 'MIN_RESEARCH_TURNS' must be an integer. Current value: {min_turns}",
                })

            max_iterations = general.get("MAX_RESEARCH_ITERATIONS")
            if max_iterations is None:
                issues.append({
                    "severity": "WARNING",
                    "message": "Setting 'MAX_RESEARCH_ITERATIONS' is missing. Using default (2).",
                })
            elif not str(max_iterations).isdigit():
                issues.append({
                    "severity": "ERROR",
                    "message": f"Setting 'MAX_RESEARCH_ITERATIONS' must be an integer. Current value: {max_iterations}",
                })

            max_versions = general.get("MAX_ARTIFACT_VERSIONS")
            if max_versions is None:
                issues.append({
                    "severity": "WARNING",
                    "message": "Setting 'MAX_ARTIFACT_VERSIONS' is missing. Using default (10).",
                })
            elif not str(max_versions).isdigit():
                issues.append({
                    "severity": "ERROR",
                    "message": f"Setting 'MAX_ARTIFACT_VERSIONS' must be an integer. Current value: {max_versions}",
                })

            # 2. Validate Providers
            providers = all_settings.get("providers", [])
            provider_ids = {p["id"] for p in providers}
            for p in providers:
                if not p["keys"]:
                    issues.append({
                        "severity": "WARNING",
                        "message": f"Provider '{p['name']}' has no API keys configured.",
                    })

                # Fix PERF401 & E501
                issues.extend([
                    {"severity": "WARNING", "message": f"Provider '{p['name']}' has an empty API key."}
                    for k in p["keys"] if not k["api_key"]
                ])

                if p["provider_type"] != "custom" and not p["base_url"]:
                    issues.append({
                        "severity": "ERROR",
                        "message": f"Provider '{p['name']}' is missing base_url.",
                    })

            # 3. Validate Agent Routes
            routes = all_settings.get("agent_routes", [])
            for r in routes:
                if r["provider_id"] not in provider_ids:
                    issues.append({
                        "severity": "ERROR",
                        "message": (
                            f"Route for '{r['task_type']}' points to "
                            f"non-existent provider ID {r['provider_id']}."
                        ),
                    })
                if not r["models"]:
                    issues.append({
                        "severity": "WARNING",
                        "message": f"Route for '{r['task_type']}' has no models specified.",
                    })

            return issues
        finally:
            if not self.session:
                session.close()

    def copy_default_routes_to_agent(self, agent_name: str) -> list[dict[str, Any]]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            default_routes = repo.get_agent_routes_by_task_type("DEFAULT")
            new_routes = []
            for dr in default_routes:
                from app.db.schema import AgentRouteFallback

                route = AgentRouteFallback(
                    task_type=agent_name,
                    provider_id=dr.provider_id,
                    models=dr.models,
                    priority=dr.priority,
                )
                repo.upsert_route(route)
                session.flush()
                new_routes.append(
                    {
                        "id": route.id,
                        "task_type": route.task_type,
                        "provider_id": route.provider_id,
                        "models": route.models,
                        "priority": route.priority,
                    }
                )
            session.commit()
            return new_routes
        finally:
            if not self.session:
                session.close()

    def reorder_routes(self, route_ids: list[int]) -> None:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            for idx, rid in enumerate(route_ids):
                route = repo.get_route_by_id(rid)
                if route:
                    route.priority = idx
                    session.add(route)
            session.commit()
        finally:
            if not self.session:
                session.close()

    def get_agent_routes(self) -> list[dict[str, Any]]:
        session = self.session or Session(settings_engine)
        try:
            routes = SettingsRepository(session).get_agent_routes()
            return [
                {
                    "id": r.id,
                    "task_type": r.task_type,
                    "provider_id": r.provider_id,
                    "models": r.models,
                    "priority": r.priority,
                }
                for r in routes
            ]
        finally:
            if not self.session:
                session.close()

    def get_providers(self) -> list[dict[str, Any]]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            providers = repo.get_providers()
            provider_list = []
            for p in providers:
                assert p.id is not None
                keys = repo.get_keys_for_provider(p.id)
                provider_list.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "provider_type": p.provider_type,
                        "base_url": p.base_url,
                        "models": p.models,
                        "keys": [
                            {"id": k.id, "api_key": k.api_key, "priority": k.priority}
                            for k in keys
                        ],
                    }
                )
            return provider_list
        finally:
            if not self.session:
                session.close()

    def reset_candidate_health(self):
        session = self.session or Session(operational_engine)
        try:
            SettingsRepository(session).reset_candidate_health()
            session.commit()
        finally:
            if not self.session:
                session.close()

    def close(self):
        """No-op. Internal sessions are closed per-method-call."""
