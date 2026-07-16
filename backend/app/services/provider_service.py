from typing import Any

from sqlmodel import Session

from app.db.schema import ProviderConfig
from app.db.settings_session import settings_engine
from app.repositories.settings import SettingsRepository


class ProviderService:
    def __init__(self, session: Session | None = None):
        self.session = session

    def get_providers(self) -> list[dict[str, Any]]:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            providers = repo.get_providers()
            provider_list = []
            for p in providers:
                if p.id is None:
                    raise ValueError("Provider record missing ID")
                keys = repo.get_keys_for_provider(p.id)
                provider_list.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "provider_type": p.provider_type,
                        "base_url": p.base_url,
                        "models": p.models,
                        "api_keys": [
                            {"id": k.id, "api_key": k.api_key, "priority": k.priority}
                            for k in keys
                        ],
                    }
                )
            return provider_list
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
            if updated.id is None:
                raise ValueError("Provider key failed to generate ID after upsert")
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

    def sync_provider_models(self, provider_id: int) -> str:
        session = self.session or Session(settings_engine)
        try:
            repo = SettingsRepository(session)
            provider = repo.get_provider_by_id(provider_id)
            if not provider:
                raise ValueError("Provider not found")

            keys = repo.get_keys_for_provider(provider_id)
            api_key = keys[0].api_key if keys else None
            base_url = (provider.base_url or "").rstrip("/")
            ptype = (provider.provider_type or "").lower()

            if ptype == "gemini" and api_key:
                import httpx
                resp = httpx.get(
                    f"{base_url}/models",
                    params={"key": api_key},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                models = [
                    m["name"].replace("models/", "")
                    for m in data.get("models", [])
                    if "name" in m
                ]
                return ", ".join(sorted(models))

            if ptype == "openai" and api_key and base_url:
                import httpx
                resp = httpx.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", []) if "id" in m]
                return ", ".join(sorted(models))

            if ptype == "anthropic" and api_key:
                import httpx
                resp = httpx.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", []) if "id" in m]
                return ", ".join(sorted(models))

            if ptype == "groq" and api_key:
                import httpx
                resp = httpx.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                models = [m["id"] for m in data.get("data", []) if "id" in m]
                return ", ".join(sorted(models))

            if base_url:
                import httpx
                try:
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    resp = httpx.get(
                        f"{base_url}/models",
                        headers=headers,
                        timeout=10,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    models = (
                        [m["id"] for m in data.get("data", []) if "id" in m]
                        or [m["name"] for m in data.get("models", []) if "name" in m]
                    )
                    if models:
                        return ", ".join(sorted(models))
                except Exception:
                    pass

            return "No models synced"
        finally:
            if not self.session:
                session.close()
