from typing import List, Optional, Sequence
from sqlmodel import Session, select, delete
from app.db.schema import Setting, ProviderConfig, ProviderKey, AgentRouteFallback, ModelConfig, CandidateHealth

class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_setting(self, key: str) -> Optional[Setting]:
        return self.session.get(Setting, key)

    def get_all_settings(self) -> Sequence[Setting]:
        return self.session.exec(select(Setting)).all()

    def upsert_setting(self, key: str, value: Optional[str]) -> Setting:
        setting = self.get_setting(key)
        if not setting:
            setting = Setting(key=key, value=value)
        else:
            setting.value = value
        self.session.add(setting)
        self.session.commit()
        self.session.refresh(setting)
        return setting

    def get_providers(self) -> Sequence[ProviderConfig]:
        return self.session.exec(select(ProviderConfig)).all()

    def get_provider_by_id(self, provider_id: int) -> Optional[ProviderConfig]:
        return self.session.get(ProviderConfig, provider_id)

    def get_provider_by_name(self, name: str) -> Optional[ProviderConfig]:
        return self.session.exec(select(ProviderConfig).where(ProviderConfig.name == name)).first()

    def upsert_provider(self, provider: ProviderConfig) -> ProviderConfig:
        self.session.add(provider)
        self.session.commit()
        self.session.refresh(provider)
        return provider

    def delete_provider(self, provider_id: int):
        provider = self.get_provider_by_id(provider_id)
        if provider:
            self.session.delete(provider)
            self.session.commit()

    def get_keys_for_provider(self, provider_id: int) -> Sequence[ProviderKey]:
        return self.session.exec(select(ProviderKey).where(ProviderKey.provider_id == provider_id).order_by(ProviderKey.priority)).all()

    def upsert_key(self, key: ProviderKey) -> ProviderKey:
        self.session.add(key)
        self.session.commit()
        self.session.refresh(key)
        return key

    def delete_key(self, key_id: int):
        key = self.session.get(ProviderKey, key_id)
        if key:
            self.session.delete(key)
            self.session.commit()

    def get_agent_routes(self) -> Sequence[AgentRouteFallback]:
        return self.session.exec(select(AgentRouteFallback).order_by(AgentRouteFallback.priority)).all()

    def get_route_by_id(self, route_id: int) -> Optional[AgentRouteFallback]:
        return self.session.get(AgentRouteFallback, route_id)

    def upsert_route(self, route: AgentRouteFallback) -> AgentRouteFallback:
        self.session.add(route)
        self.session.commit()
        self.session.refresh(route)
        return route

    def delete_route(self, route_id: int):
        route = self.get_route_by_id(route_id)
        if route:
            self.session.delete(route)
            self.session.commit()

    def reset_candidate_health(self):
        self.session.exec(delete(CandidateHealth))
        self.session.commit()
