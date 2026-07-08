import pytest


SETTINGS = "/settings"


class TestSettingsPage:
    def test_settings_page(self, api_client):
        r = api_client.get(SETTINGS)
        assert r.status_code == 200

    def test_general_tab(self, api_client):
        r = api_client.get(f"{SETTINGS}/tab/general")
        assert r.status_code == 200

    def test_providers_tab(self, api_client):
        r = api_client.get(f"{SETTINGS}/tab/providers")
        assert r.status_code == 200

    def test_routes_tab(self, api_client):
        r = api_client.get(f"{SETTINGS}/tab/routes")
        assert r.status_code == 200

    def test_health_tab(self, api_client):
        r = api_client.get(f"{SETTINGS}/tab/health")
        assert r.status_code == 200


class TestSettingsGeneral:
    def test_update_setting(self, api_client):
        r = api_client.post(
            f"{SETTINGS}/general/update",
            data={"key": "test_key", "value": "test_val"},
        )
        assert r.status_code == 200
        assert "HX-Trigger" in r.headers
        assert '"showToast": {"value": "Setting updated", "type": "info"}' in r.headers["HX-Trigger"]

    def test_delete_setting(self, api_client):
        r = api_client.post(
            f"{SETTINGS}/general/delete",
            data={"key": "test_key_del"},
        )
        assert r.status_code == 200


class TestSettingsProviders:
    def test_create_provider(self, api_client):
        r = api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={
                "name": "UI Test Provider",
                "provider_type": "openai",
                "base_url": "https://api.test.com",
                "models": "gpt-4,gpt-3.5",
            },
        )
        assert r.status_code == 200
        assert "HX-Trigger" in r.headers
        assert '"showToast": {"value": "Provider updated", "type": "info"}' in r.headers["HX-Trigger"]

    def test_update_provider(self, api_client, clean_db):
        # Create provider first via API
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "UpdateMe", "provider_type": "anthropic"},
        )
        # Now update it — need to get its ID from settings DB
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "UpdateMe")).first()
            pid = p.id
        r = api_client.post(
            f"{SETTINGS}/providers/{pid}/update",
            data={"name": "Updated", "models": "claude-4"},
        )
        assert r.status_code == 200

    def test_delete_provider(self, api_client, clean_db):
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "DelMe", "provider_type": "azure"},
        )
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "DelMe")).first()
            pid = p.id
        r = api_client.post(f"{SETTINGS}/providers/{pid}/delete")
        assert r.status_code == 200

    def test_add_key_to_provider(self, api_client, clean_db):
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "KeyProv", "provider_type": "openai"},
        )
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "KeyProv")).first()
            pid = p.id
        r = api_client.post(
            f"{SETTINGS}/providers/{pid}/keys",
            data={"api_key": "sk-test", "priority": 1},
        )
        assert r.status_code == 200

    def test_edit_key(self, api_client, clean_db):
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "EditKeyProv", "provider_type": "openai"},
        )
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig, ProviderKey
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "EditKeyProv")).first()
            pid = p.id
            # create a key
            from app.repositories.settings import SettingsRepository
            repo = SettingsRepository(session)
            repo.upsert_key(ProviderKey(provider_id=pid, api_key="old-key", priority=0))
            session.commit()
            k = session.exec(select(ProviderKey).where(ProviderKey.provider_id == pid)).first()
            kid = k.id
        r = api_client.post(
            f"{SETTINGS}/providers/{pid}/keys/{kid}/edit",
            data={"api_key": "new-key", "priority": 2},
        )
        assert r.status_code == 200

    def test_delete_key(self, api_client, clean_db):
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "DelKeyProv", "provider_type": "openai"},
        )
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig, ProviderKey
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "DelKeyProv")).first()
            pid = p.id
            from app.repositories.settings import SettingsRepository
            repo = SettingsRepository(session)
            repo.upsert_key(ProviderKey(provider_id=pid, api_key="del-key", priority=0))
            session.commit()
            k = session.exec(select(ProviderKey).where(ProviderKey.provider_id == pid)).first()
            kid = k.id
        r = api_client.post(f"{SETTINGS}/providers/{pid}/keys/{kid}/delete")
        assert r.status_code == 200


class TestSettingsRoutes:
    def test_create_route(self, api_client, clean_db):
        # Need a provider first
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "RouteProv", "provider_type": "openai"},
        )
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "RouteProv")).first()
            pid = p.id
        r = api_client.post(
            f"{SETTINGS}/routes/upsert",
            data={
                "task_type": "test_route",
                "provider_id": pid,
                "models": "gpt-4",
                "priority": 1,
            },
        )
        assert r.status_code == 200
        assert "HX-Trigger" in r.headers
        assert '"showToast": {"value": "Route updated", "type": "info"}' in r.headers["HX-Trigger"]

    def test_delete_route(self, api_client, clean_db):
        api_client.post(
            f"{SETTINGS}/providers/upsert",
            data={"name": "DelRouteProv", "provider_type": "openai"},
        )
        from app.db.settings_session import settings_engine
        from sqlmodel import Session, select
        from app.db.schema import ProviderConfig, AgentRouteFallback
        with Session(settings_engine) as session:
            p = session.exec(select(ProviderConfig).where(ProviderConfig.name == "DelRouteProv")).first()
            pid = p.id
            from app.repositories.settings import SettingsRepository
            repo = SettingsRepository(session)
            repo.upsert_route(AgentRouteFallback(
                task_type="del_route", provider_id=pid, models="gpt-4", priority=0
            ))
            session.commit()
            route = session.exec(select(AgentRouteFallback).where(AgentRouteFallback.task_type == "del_route")).first()
            rid = route.id
        r = api_client.post(f"{SETTINGS}/routes/{rid}/delete")
        assert r.status_code == 200

    def test_route_override(self, api_client):
        r = api_client.post(f"{SETTINGS}/routes/Researcher/override")
        assert r.status_code == 200

    def test_route_reorder(self, api_client, clean_db):
        r = api_client.post(
            f"{SETTINGS}/routes/reorder",
            data={"route_ids": "[]"},
        )
        assert r.status_code == 200


class TestSettingsHealth:
    def test_reset_health(self, api_client):
        r = api_client.post(f"{SETTINGS}/reset-health")
        assert r.status_code == 200
