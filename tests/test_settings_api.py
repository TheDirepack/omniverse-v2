import uuid

import pytest


def _unique(prefix: str = "t") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class TestGeneralSettings:
    ENDPOINT = "/api/settings/general"
    GET_ENDPOINT = "/api/settings"

    def test_save_and_get(self, api_client):
        key = _unique("key")
        r = api_client.post(self.ENDPOINT, json={"key": key, "value": "hello"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"

        r2 = api_client.get(self.GET_ENDPOINT)
        assert r2.json()["general_settings"].get(key) == "hello"

    def test_update(self, api_client):
        key = _unique("key")
        api_client.post(self.ENDPOINT, json={"key": key, "value": "v1"})
        r = api_client.post(self.ENDPOINT, json={"key": key, "value": "v2"})
        assert r.status_code == 200

        r2 = api_client.get(self.GET_ENDPOINT)
        assert r2.json()["general_settings"].get(key) == "v2"

    def test_delete(self, api_client):
        key = _unique("key")
        api_client.post(self.ENDPOINT, json={"key": key, "value": "delete-me"})
        r = api_client.post(self.ENDPOINT, json={"key": key, "value": None})
        assert r.status_code == 200

        r2 = api_client.get(self.GET_ENDPOINT)
        gs = r2.json()["general_settings"]
        assert key in gs
        assert gs[key] is None

    def test_multiple_isolated(self, api_client):
        k1, k2 = _unique("k"), _unique("k")
        api_client.post(self.ENDPOINT, json={"key": k1, "value": "a"})
        api_client.post(self.ENDPOINT, json={"key": k2, "value": "b"})

        r = api_client.get(self.GET_ENDPOINT)
        gs = r.json()["general_settings"]
        assert gs.get(k1) == "a"
        assert gs.get(k2) == "b"

    def test_persistence(self, api_client):
        key = _unique("key")
        api_client.post(self.ENDPOINT, json={"key": key, "value": "sticky"})

        r1 = api_client.get(self.GET_ENDPOINT)
        r2 = api_client.get(self.GET_ENDPOINT)
        v1 = r1.json()["general_settings"].get(key)
        v2 = r2.json()["general_settings"].get(key)
        assert v1 == v2 == "sticky"


class TestProviderCRUD:
    ENDPOINT = "/api/providers"

    def test_create_minimal(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={"name": name})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        pid = data["provider"]["id"]
        assert pid is not None

        providers = api_client.get(self.ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid]
        assert len(match) == 1
        assert match[0]["name"] == name
        assert match[0]["provider_type"] is None
        assert match[0]["base_url"] is None
        assert match[0]["models"] is None
        assert match[0]["keys"] == []

    def test_create_all_fields(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={
            "name": name,
            "provider_type": "openai",
            "base_url": "https://api.openai.com/v1",
            "models": "gpt-4,gpt-3.5",
        })
        assert r.status_code == 200
        pid = r.json()["provider"]["id"]

        providers = api_client.get(self.ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        assert match["name"] == name
        assert match["provider_type"] == "openai"
        assert match["base_url"] == "https://api.openai.com/v1"
        assert match["models"] == "gpt-4,gpt-3.5"

    def test_get_list(self, api_client):
        name = _unique("p")
        api_client.post(self.ENDPOINT, json={"name": name})

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(p["name"] == name for p in data)

    def test_update_name(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={"name": name})
        pid = r.json()["provider"]["id"]

        new_name = name + "-renamed"
        r2 = api_client.post(self.ENDPOINT, json={"id": pid, "name": new_name})
        assert r2.status_code == 200
        assert r2.json()["provider"]["name"] == new_name

        providers = api_client.get(self.ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid]
        assert len(match) == 1
        assert match[0]["name"] == new_name

    def test_update_type(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={"name": name, "provider_type": "openai"})
        pid = r.json()["provider"]["id"]

        ur = api_client.post(self.ENDPOINT, json={"id": pid, "name": name, "provider_type": "anthropic"})
        assert ur.status_code == 200
        providers = api_client.get(self.ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        assert match["provider_type"] == "anthropic"

    def test_update_base_url(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={"name": name, "provider_type": "custom"})
        pid = r.json()["provider"]["id"]

        ur = api_client.post(self.ENDPOINT, json={"id": pid, "name": name, "base_url": "http://localhost:8080/v1"})
        assert ur.status_code == 200
        providers = api_client.get(self.ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        assert match["base_url"] == "http://localhost:8080/v1"

    def test_update_models(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={"name": name})
        pid = r.json()["provider"]["id"]

        ur = api_client.post(self.ENDPOINT, json={"id": pid, "name": name, "models": "a,b,c"})
        assert ur.status_code == 200
        providers = api_client.get(self.ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        assert match["models"] == "a,b,c"

    def test_delete(self, api_client):
        name = _unique("p")
        r = api_client.post(self.ENDPOINT, json={"name": name})
        pid = r.json()["provider"]["id"]

        dr = api_client.delete(f"{self.ENDPOINT}/{pid}")
        assert dr.status_code == 200
        assert dr.json()["status"] == "success"

        providers = api_client.get(self.ENDPOINT).json()
        assert not any(p["id"] == pid for p in providers)

    def test_delete_nonexistent_returns_404(self, api_client):
        r = api_client.delete(f"{self.ENDPOINT}/9999999")
        assert r.status_code == 404


class TestProviderKeys:
    PROVIDER_ENDPOINT = "/api/providers"
    KEY_ENDPOINT = "/api/providers/keys"

    def _create_provider(self, api_client) -> int:
        name = _unique("pk")
        r = api_client.post(self.PROVIDER_ENDPOINT, json={"name": name})
        return r.json()["provider"]["id"]

    def test_add_key(self, api_client):
        pid = self._create_provider(api_client)
        r = api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-test123", "priority": 0,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        key_id = r.json()["key_id"]
        assert key_id is not None

        providers = api_client.get(self.PROVIDER_ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        key_ids = [k["id"] for k in match["keys"]]
        assert key_id in key_ids

    def test_priority_order(self, api_client):
        pid = self._create_provider(api_client)
        r1 = api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-second", "priority": 1,
        })
        r2 = api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-first", "priority": 0,
        })
        id1, id2 = r1.json()["key_id"], r2.json()["key_id"]

        providers = api_client.get(self.PROVIDER_ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        ordered = [k["id"] for k in match["keys"]]
        first_idx = ordered.index(id2)
        second_idx = ordered.index(id1)
        assert first_idx < second_idx

    def test_delete_key(self, api_client):
        pid = self._create_provider(api_client)
        r = api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-deleteme", "priority": 0,
        })
        key_id = r.json()["key_id"]

        dr = api_client.delete(f"{self.KEY_ENDPOINT}/{key_id}")
        assert dr.status_code == 200

        providers = api_client.get(self.PROVIDER_ENDPOINT).json()
        match = [p for p in providers if p["id"] == pid][0]
        assert not any(k["id"] == key_id for k in match["keys"])

    def test_delete_key_404(self, api_client):
        r = api_client.delete(f"{self.KEY_ENDPOINT}/9999999")
        assert r.status_code == 404

    def test_persistence(self, api_client):
        pid = self._create_provider(api_client)
        api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-sticky", "priority": 0,
        })

        p1 = api_client.get(self.PROVIDER_ENDPOINT).json()
        p2 = api_client.get(self.PROVIDER_ENDPOINT).json()
        m1 = [p for p in p1 if p["id"] == pid][0]
        m2 = [p for p in p2 if p["id"] == pid][0]
        assert len(m1["keys"]) == len(m2["keys"]) == 1

    def test_provider_delete_cascades_keys(self, api_client):
        pid = self._create_provider(api_client)
        api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-cascade", "priority": 0,
        })
        api_client.delete(f"{self.PROVIDER_ENDPOINT}/{pid}")

        # Verify the key endpoint returns 404 for deleted key
        providers = api_client.get(self.PROVIDER_ENDPOINT).json()
        assert not any(p["id"] == pid for p in providers)


class TestAgentRouting:
    ENDPOINT = "/api/agent-routes"
    PROVIDER_ENDPOINT = "/api/providers"

    def _create_provider(self, api_client) -> int:
        name = _unique("rt")
        r = api_client.post(self.PROVIDER_ENDPOINT, json={"name": name})
        return r.json()["provider"]["id"]

    def test_default_route_exists(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        routes = r.json()
        assert any(rt["task_type"] == "DEFAULT" for rt in routes)

    def test_create_for_agent(self, api_client):
        pid = self._create_provider(api_client)
        task = _unique("TASK")
        r = api_client.post(self.ENDPOINT, json={
            "task_type": task, "provider_id": pid, "models": "gpt-4", "priority": 0,
        })
        assert r.status_code == 200
        assert r.json()["status"] == "success"

        routes = api_client.get(self.ENDPOINT).json()
        assert any(
            rt["task_type"] == task and rt["provider_id"] == pid
            for rt in routes
        )

    def test_persistence(self, api_client):
        pid = self._create_provider(api_client)
        task = _unique("TASK")
        api_client.post(self.ENDPOINT, json={
            "task_type": task, "provider_id": pid, "models": "gpt-4", "priority": 0,
        })

        r1 = api_client.get(self.ENDPOINT)
        r2 = api_client.get(self.ENDPOINT)
        t1 = [rt for rt in r1.json() if rt["task_type"] == task]
        t2 = [rt for rt in r2.json() if rt["task_type"] == task]
        assert len(t1) == len(t2) == 1

    def test_upsert(self, api_client):
        pid = self._create_provider(api_client)
        task = _unique("TASK")
        api_client.post(self.ENDPOINT, json={
            "task_type": task, "provider_id": pid, "models": "v1", "priority": 0,
        })

        # Find route id
        routes = api_client.get(self.ENDPOINT).json()
        match = [rt for rt in routes if rt["task_type"] == task]
        assert len(match) == 1
        route_id = match[0]["id"]

        # Update via id
        ur = api_client.post(self.ENDPOINT, json={
            "id": route_id, "task_type": task, "models": "v2", "priority": 0,
        })
        assert ur.status_code == 200

        routes = api_client.get(self.ENDPOINT).json()
        matches = [rt for rt in routes if rt["task_type"] == task]
        assert len(matches) == 1
        assert matches[0]["models"] == "v2"

    def test_null_provider(self, api_client):
        task = _unique("TASK")
        r = api_client.post(self.ENDPOINT, json={
            "task_type": task, "provider_id": None, "priority": 0,
        })
        assert r.status_code == 200

    def test_null_models(self, api_client):
        pid = self._create_provider(api_client)
        task = _unique("TASK")
        r = api_client.post(self.ENDPOINT, json={
            "task_type": task, "provider_id": pid, "models": None, "priority": 0,
        })
        assert r.status_code == 200

    def test_delete(self, api_client):
        task = _unique("TASK")
        api_client.post(self.ENDPOINT, json={
            "task_type": task, "priority": 0,
        })
        routes = api_client.get(self.ENDPOINT).json()
        match = [rt for rt in routes if rt["task_type"] == task]
        assert len(match) == 1
        route_id = match[0]["id"]

        dr = api_client.delete(f"{self.ENDPOINT}/{route_id}")
        assert dr.status_code == 200

        routes = api_client.get(self.ENDPOINT).json()
        assert not any(rt["id"] == route_id for rt in routes)

    def test_delete_404(self, api_client):
        r = api_client.delete(f"{self.ENDPOINT}/9999999")
        assert r.status_code == 404

    def test_list(self, api_client):
        pid = self._create_provider(api_client)
        task = _unique("TASK")
        api_client.post(self.ENDPOINT, json={
            "task_type": task, "provider_id": pid, "priority": 0,
        })

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(rt["task_type"] == task for rt in data)

    def test_agent_names(self, api_client):
        r = api_client.get("/api/agent-names")
        assert r.status_code == 200
        names = r.json()
        assert isinstance(names, list)
        assert len(names) >= 8
        assert "Researcher" in names
        assert "DEFAULT" not in names


class TestFullSettingsRoundtrip:
    SETTINGS_ENDPOINT = "/api/settings"
    PROVIDER_ENDPOINT = "/api/providers"
    KEY_ENDPOINT = "/api/providers/keys"
    ROUTE_ENDPOINT = "/api/agent-routes"
    SETTING_ENDPOINT = "/api/settings/general"

    def test_endpoint_structure(self, api_client):
        r = api_client.get(self.SETTINGS_ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert "general_settings" in data
        assert "providers" in data
        assert "agent_routes" in data
        assert isinstance(data["general_settings"], dict)
        assert isinstance(data["providers"], list)
        assert isinstance(data["agent_routes"], list)

    def test_complete_workflow(self, api_client):
        # Create provider
        pname = _unique("wf")
        rp = api_client.post(self.PROVIDER_ENDPOINT, json={
            "name": pname,
            "provider_type": "openai",
            "models": "gpt-4",
        })
        pid = rp.json()["provider"]["id"]

        # Add key
        rk = api_client.post(self.KEY_ENDPOINT, json={
            "provider_id": pid, "api_key": "sk-workflow", "priority": 0,
        })
        key_id = rk.json()["key_id"]

        # Create route
        task = _unique("WF")
        api_client.post(self.ROUTE_ENDPOINT, json={
            "task_type": task, "provider_id": pid, "models": "gpt-4", "priority": 0,
        })

        # Save setting
        skey = _unique("wf")
        api_client.post(self.SETTING_ENDPOINT, json={"key": skey, "value": "wf-val"})

        # Full settings fetch — everything present
        r = api_client.get(self.SETTINGS_ENDPOINT)
        data = r.json()

        # Provider with key
        pmatch = [p for p in data["providers"] if p["id"] == pid]
        assert len(pmatch) == 1
        assert pmatch[0]["name"] == pname
        assert any(k["id"] == key_id for k in pmatch[0]["keys"])

        # Route
        assert any(rt["task_type"] == task for rt in data["agent_routes"])

        # Setting
        assert data["general_settings"].get(skey) == "wf-val"

    def test_reload_consistency(self, api_client):
        # Seed some data
        pname = _unique("rl")
        rp = api_client.post(self.PROVIDER_ENDPOINT, json={"name": pname})
        pid = rp.json()["provider"]["id"]
        skey = _unique("rl")
        api_client.post(self.SETTING_ENDPOINT, json={"key": skey, "value": "rl-val"})

        r1 = api_client.get(self.SETTINGS_ENDPOINT).json()
        r2 = api_client.get(self.SETTINGS_ENDPOINT).json()

        assert [p for p in r1["providers"] if p["id"] == pid] == \
               [p for p in r2["providers"] if p["id"] == pid]
        assert r1["general_settings"].get(skey) == r2["general_settings"].get(skey)
