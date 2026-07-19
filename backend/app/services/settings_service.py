from typing import Any

from sqlmodel import Session

from app.db.operational_session import operational_engine
from app.db.schema import ProviderConfig, Setting
from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository
from app.services.provider_service import ProviderService
from app.services.route_service import RouteService

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
        self._provider_service = ProviderService(session=session)
        self._route_service = RouteService(session=session)

    def get_setting(self, key: str) -> Setting | None:
        session = self.session or Session(settings_engine)
        try:
            return SettingsRepository(session).get_setting(key)
        finally:
            if not self.session:
                session.close()

    def get_all_settings(self) -> dict[str, Any]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            settings = repo.get_all_settings()
            provider_details = self._provider_service.get_providers()
            routes = self._route_service.get_agent_routes()

            return {
                "general_settings": {s.key: s.value for s in settings},
                "providers": provider_details,
                "agent_routes": routes,
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

    # --- Provider delegates ---

    def get_providers(self) -> list[dict[str, Any]]:
        return self._provider_service.get_providers()

    def get_provider_by_id(self, provider_id: int) -> ProviderConfig | None:
        return self._provider_service.get_provider_by_id(provider_id)

    def upsert_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._provider_service.upsert_provider(payload)

    def upsert_provider_key(
        self,
        provider_id: int,
        api_key: str,
        priority: int = 0,
        key_id: int | None = None,
    ) -> int:
        return self._provider_service.upsert_provider_key(
            provider_id, api_key, priority, key_id,
        )

    def delete_provider_key(self, key_id: int) -> bool:
        return self._provider_service.delete_provider_key(key_id)

    def delete_provider(self, provider_id: int) -> bool:
        return self._provider_service.delete_provider(provider_id)

    def sync_provider_models(self, provider_id: int) -> str:
        return self._provider_service.sync_provider_models(provider_id)

    # --- Route delegates ---

    def get_agent_routes(self) -> list[dict[str, Any]]:
        return self._route_service.get_agent_routes()

    def get_agent_route_by_id(self, route_id: int) -> dict[str, Any] | None:
        return self._route_service.get_agent_route_by_id(route_id)

    def get_agent_route_by_task_type(self, task_type: str) -> dict[str, Any] | None:
        return self._route_service.get_agent_route_by_task_type(task_type)

    def upsert_agent_route(
        self,
        task_type: str,
        provider_id: int | None,
        models: str | None,
        priority: int = 0,
        route_id: int | None = None,
    ) -> None:
        return self._route_service.upsert_agent_route(
            task_type, provider_id, models, priority, route_id,
        )

    def delete_agent_route(self, route_id: int) -> bool:
        return self._route_service.delete_agent_route(route_id)

    def reorder_routes(self, route_ids: list[int]) -> None:
        return self._route_service.reorder_routes(route_ids)

    def copy_default_routes_to_agent(self, agent_name: str) -> list[dict[str, Any]]:
        return self._route_service.copy_default_routes_to_agent(agent_name)

    # --- Remaining methods ---

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

            max_tokens = general.get("MAX_TOKENS")
            if max_tokens is None:
                issues.append({
                    "severity": "WARNING",
                    "message": "Setting 'MAX_TOKENS' is missing. Using default (32000).",
                })
            elif not str(max_tokens).isdigit():
                issues.append({
                    "severity": "ERROR",
                    "message": f"Setting 'MAX_TOKENS' must be an integer. Current value: {max_tokens}",
                })

            comp_threshold = general.get("COMPRESSION_THRESHOLD")
            if comp_threshold is None:
                issues.append({
                    "severity": "WARNING",
                    "message": "Setting 'COMPRESSION_THRESHOLD' is missing. Using default (0.8).",
                })
            else:
                try:
                    float(comp_threshold)
                except ValueError:
                    issues.append({
                        "severity": "ERROR",
                        "message": f"Setting 'COMPRESSION_THRESHOLD' must be a float. Current value: {comp_threshold}",
                    })

            # 2. Validate Providers
            providers = all_settings.get("providers", [])
            provider_ids = {p["id"] for p in providers}
            for p in providers:
                if not p["api_keys"]:
                    issues.append({
                        "severity": "WARNING",
                        "message": f"Provider '{p['name']}' has no API keys configured.",
                    })

                issues.extend([
                    {"severity": "WARNING", "message": f"Provider '{p['name']}' has an empty API key."}
                    for k in p["api_keys"] if not k["api_key"]
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

    def reset_candidate_health(self):
        session = self.session or Session(operational_engine)
        try:
            SettingsRepository(session).reset_candidate_health()
            session.commit()
        finally:
            if not self.session:
                session.close()
