from collections.abc import Sequence

from sqlmodel import Session, delete, select

from app.db.schema import (
    AgentRouteFallback,
    CandidateHealth,
    ProviderConfig,
    ProviderKey,
    Setting,
)


class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_setting(self, key: str) -> Setting | None:
        return self.session.get(Setting, key)

    def get_all_settings(self) -> Sequence[Setting]:
        return self.session.exec(select(Setting)).all()

    def upsert_setting(self, key: str, value: str | None) -> Setting:
        setting = self.get_setting(key)
        if not setting:
            setting = Setting(key=key, value=value)
        else:
            setting.value = value
        self.session.add(setting)
        return setting

    def get_providers(self) -> Sequence[ProviderConfig]:
        return self.session.exec(select(ProviderConfig)).all()

    def get_provider_by_id(self, provider_id: int) -> ProviderConfig | None:
        return self.session.get(ProviderConfig, provider_id)

    def get_provider_by_name(self, name: str) -> ProviderConfig | None:
        return self.session.exec(
            select(ProviderConfig).where(ProviderConfig.name == name)
        ).first()

    def upsert_provider(self, provider: ProviderConfig) -> ProviderConfig:
        self.session.add(provider)
        return provider

    def delete_provider(self, provider_id: int) -> bool:
        provider = self.get_provider_by_id(provider_id)
        if provider:
            self.session.delete(provider)
            return True
        return False

    def get_keys_for_provider(self, provider_id: int) -> Sequence[ProviderKey]:
        return self.session.exec(
            select(ProviderKey)
            .where(ProviderKey.provider_id == provider_id)
            .order_by(ProviderKey.priority)
        ).all()

    def get_all_keys(self) -> Sequence[ProviderKey]:
        return self.session.exec(select(ProviderKey)).all()

    def upsert_key(self, key: ProviderKey) -> ProviderKey:
        self.session.add(key)
        return key

    def delete_key(self, key_id: int) -> bool:
        key = self.session.get(ProviderKey, key_id)
        if key:
            self.session.delete(key)
            return True
        return False

    def get_agent_routes(self) -> Sequence[AgentRouteFallback]:
        return self.session.exec(
            select(AgentRouteFallback).order_by(AgentRouteFallback.priority)
        ).all()

    def get_agent_routes_by_task_type(
        self, task_type: str
    ) -> Sequence[AgentRouteFallback]:
        return self.session.exec(
            select(AgentRouteFallback)
            .where(AgentRouteFallback.task_type == task_type)
            .order_by(AgentRouteFallback.priority)
        ).all()

    def get_route_by_id(self, route_id: int) -> AgentRouteFallback | None:
        return self.session.get(AgentRouteFallback, route_id)

    def upsert_route(self, route: AgentRouteFallback) -> AgentRouteFallback:
        self.session.add(route)
        return route

    def delete_route(self, route_id: int) -> bool:
        route = self.get_route_by_id(route_id)
        if route:
            self.session.delete(route)
            self.session.commit()
            return True
        return False

    def reset_candidate_health(self):
        self.session.exec(delete(CandidateHealth))
        self.session.commit()

    def bootstrap_default_settings(self):
        """Initialize default settings if not present."""
        existing = self.get_all_settings()
        existing_keys = {s.key for s in existing}

        defaults = {
            "MIN_RESEARCH_TURNS": "6",
            "MAX_PARALLEL_AGENTS": "5",
            "AGENT_LOGGING": "false",
            "HIDE_WEBFETCH_CONTENT": "false",
            "HIDE_WEBSEARCH_CONTENT": "false",
            "BROWSER_POOL_SIZE": "2",
            "BROWSER_MAX_CONCURRENCY_PER_INSTANCE": "5",
            "MAX_TOKENS": "32000",
            "COMPRESSION_THRESHOLD": "0.8",
        }

        for key, value in defaults.items():
            if key not in existing_keys:
                setting = Setting(key=key, value=value)
                self.session.add(setting)

        # Bootstrap default provider if no providers exist
        existing_providers = self.get_providers()
        if not existing_providers:
            provider = ProviderConfig(
                name="DEFAULT",
                provider_type="custom",
                base_url="http://localhost:8001",
                models="gpt-4o,gpt-4o-mini,claude-3.5",
            )
            self.session.add(provider)
            provider_id = provider.id
            self.session.flush()

            # Bootstrap default route
            self.upsert_route(
                AgentRouteFallback(
                    task_type="DEFAULT",
                    priority=0,
                    provider_id=provider_id,
                    models="gpt-4o,gpt-4o-mini,claude-3.5",
                )
            )
