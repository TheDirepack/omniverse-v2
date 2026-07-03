import pytest


class TestSettingsGeneral:
    ENDPOINT = "/api/settings/general"

    def test_missing_key(self, client):
        r = client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_key_empty(self, client):
        r = client.post(self.ENDPOINT, json={"key": "", "value": "v"})
        assert r.status_code == 200

    def test_key_very_long(self, client):
        r = client.post(self.ENDPOINT, json={"key": "A" * 10000, "value": "v"})
        assert r.status_code == 200

    def test_key_with_xss(self, client):
        r = client.post(self.ENDPOINT, json={"key": "<script>alert(1)</script>", "value": "x"})
        assert r.status_code == 200

    def test_key_unicode(self, client):
        r = client.post(self.ENDPOINT, json={"key": "🔑-setting", "value": "emoji"})
        assert r.status_code == 200

    def test_value_null(self, client):
        r = client.post(self.ENDPOINT, json={"key": "nullable", "value": None})
        assert r.status_code == 200

    def test_value_empty(self, client):
        r = client.post(self.ENDPOINT, json={"key": "empty-val", "value": ""})
        assert r.status_code == 200

    def test_value_very_long(self, client):
        r = client.post(self.ENDPOINT, json={"key": "long", "value": "A" * 100_000})
        assert r.status_code == 200

    def test_key_null(self, client):
        r = client.post(self.ENDPOINT, json={"key": None, "value": "v"})
        assert r.status_code == 422

    def test_response_body(self, client):
        r = client.post(self.ENDPOINT, json={"key": "mykey", "value": "myval"})
        data = r.json()
        assert data["status"] == "success"
        assert "mykey" in data["message"]


class TestProviders:
    ENDPOINT = "/api/providers"

    def test_missing_name(self, client):
        r = client.post(self.ENDPOINT, json={"provider_type": "openai"})
        assert r.status_code == 422

    def test_name_empty(self, client):
        r = client.post(self.ENDPOINT, json={"name": ""})
        assert r.status_code == 200

    def test_name_xss(self, client):
        r = client.post(self.ENDPOINT, json={"name": "<img onerror=alert(1)>"})
        assert r.status_code == 200

    def test_name_unicode(self, client):
        r = client.post(self.ENDPOINT, json={"name": "提供者"})
        assert r.status_code == 200

    def test_name_very_long(self, client):
        r = client.post(self.ENDPOINT, json={"name": "A" * 500})
        assert r.status_code == 200

    def test_id_zero(self, client):
        r = client.post(self.ENDPOINT, json={"id": 0, "name": "zero-id"})
        assert r.status_code == 200
        data = r.json()
        assert data["provider"]["id"] is not None

    def test_id_negative(self, client):
        r = client.post(self.ENDPOINT, json={"id": -1, "name": "neg-id"})
        assert r.status_code == 200

    def test_id_nonexistent(self, client):
        r = client.post(self.ENDPOINT, json={"id": 9999, "name": "bad-id"})
        # Creates new, ignoring id 9999 since it doesn't exist
        assert r.status_code == 200

    def test_provider_type_empty(self, client):
        r = client.post(self.ENDPOINT, json={"name": "empty-type", "provider_type": ""})
        assert r.status_code == 200

    def test_api_key_null(self, client):
        r = client.post(self.ENDPOINT, json={"name": "null-key", "api_key": None})
        assert r.status_code == 200

    def test_base_url_malformed(self, client):
        r = client.post(self.ENDPOINT, json={"name": "bad-url", "base_url": "not-a-url"})
        assert r.status_code == 200

    def test_models_empty(self, client):
        r = client.post(self.ENDPOINT, json={"name": "no-models", "models": ""})
        assert r.status_code == 200

    def test_models_csv(self, client):
        r = client.post(self.ENDPOINT, json={"name": "csv-models", "models": "gpt-4,gpt-3.5"})
        assert r.status_code == 200

    def test_models_with_spaces(self, client):
        r = client.post(self.ENDPOINT, json={"name": "space-models", "models": "gpt-4, gpt-3.5"})
        assert r.status_code == 200

    def test_duplicate_name(self, client):
        r1 = client.post(self.ENDPOINT, json={"name": "dup-prove"})
        assert r1.status_code == 200
        r2 = client.post(self.ENDPOINT, json={"name": "dup-prove", "provider_type": "anthropic"})
        assert r2.status_code == 200

    def test_minimal_payload(self, client):
        r = client.post(self.ENDPOINT, json={"name": "minimal"})
        assert r.status_code == 200

    def test_get_empty(self, client):
        r = client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert r.json() == []

    def test_get_after_create(self, client):
        client.post(self.ENDPOINT, json={"name": "get-test", "provider_type": "openai"})
        r = client.get(self.ENDPOINT)
        data = r.json()
        assert len(data) >= 1
        assert any(p["name"] == "get-test" for p in data)

    def test_get_provider_models_nonexistent(self, client):
        r = client.get(f"{self.ENDPOINT}/9999/models")
        assert r.status_code == 200
        assert r.json()["models"] == []

    def test_get_provider_models_negative(self, client):
        r = client.get(f"{self.ENDPOINT}/-1/models")
        assert r.status_code == 200
        assert r.json()["models"] == []

    def test_get_provider_models_non_int(self, client):
        r = client.get(f"{self.ENDPOINT}/abc/models")
        assert r.status_code == 422


class TestAgentRoutes:
    ENDPOINT = "/api/agent-routes"

    def test_missing_task_type(self, client):
        r = client.post(self.ENDPOINT, json={"provider_id": 1})
        assert r.status_code == 422

    def test_task_type_empty(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": ""})
        assert r.status_code == 422

    def test_task_type_unknown(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "NONEXISTENT"})
        assert r.status_code == 200

    def test_task_type_very_long(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "A" * 500})
        assert r.status_code == 200

    def test_provider_id_null(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "NULL_PROV", "provider_id": None})
        assert r.status_code == 200

    def test_provider_id_zero(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "ZERO_PROV", "provider_id": 0})
        assert r.status_code == 422

    def test_provider_id_nonexistent(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "BAD_FK", "provider_id": 9999})
        assert r.status_code == 422

    def test_model_name_null(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "NULL_MODEL", "model_name": None})
        assert r.status_code == 200

    def test_model_name_empty(self, client):
        r = client.post(self.ENDPOINT, json={"task_type": "EMPTY_MODEL", "model_name": ""})
        assert r.status_code == 200

    def test_duplicate_task_type_upsert(self, client):
        client.post(self.ENDPOINT, json={"task_type": "UPSERT", "model_name": "v1"})
        r = client.post(self.ENDPOINT, json={"task_type": "UPSERT", "model_name": "v2"})
        assert r.status_code == 200

    def test_get_empty(self, client):
        r = client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert r.json() == []

    def test_get_after_create(self, client):
        client.post(self.ENDPOINT, json={"task_type": "GET_TEST"})
        r = client.get(self.ENDPOINT)
        assert any(route["task_type"] == "GET_TEST" for route in r.json())


class TestWorlds:
    ENDPOINT = "/api/worlds"

    def test_missing_world_name(self, client):
        r = client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_world_name_empty(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": ""})
        assert r.status_code == 200

    def test_world_name_very_long(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "A" * 500})
        assert r.status_code == 200

    def test_world_name_xss(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "<script>alert('xss')</script>"})
        assert r.status_code == 200

    def test_world_name_null(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": None})
        assert r.status_code == 422

    def test_duplicate_world_name(self, client):
        client.post(self.ENDPOINT, json={"world_name": "DuplicateWorld", "auto_research": False})
        r = client.post(self.ENDPOINT, json={"world_name": "DuplicateWorld", "auto_research": False})
        assert r.status_code == 200

    def test_auto_research_false(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "ManualWorld", "auto_research": False})
        assert r.status_code == 200
        assert r.json()["status"] == "created"

    def test_auto_research_null(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "NullAuto", "auto_research": None})
        assert r.status_code == 422

    def test_auto_research_not_bool(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "BadAuto", "auto_research": "yes"})
        assert r.status_code == 200

    def test_auto_research_omitted(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "OmittedAuto"})
        assert r.status_code == 200
        assert r.json()["status"] == "queued"

    def test_get_empty(self, client):
        r = client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert r.json() == []

    def test_get_after_create(self, client):
        client.post(self.ENDPOINT, json={"world_name": "GetTest", "auto_research": False})
        r = client.get(self.ENDPOINT)
        names = [w["name"] for w in r.json()]
        assert "GetTest" in names

    def test_clear_explored_nonexistent(self, client):
        r = client.post(f"{self.ENDPOINT}/99999/clear-explored")
        assert r.status_code == 404

    def test_clear_explored_negative(self, client):
        r = client.post(f"{self.ENDPOINT}/-1/clear-explored")
        assert r.status_code == 404

    def test_clear_explored_non_int(self, client):
        r = client.post(f"{self.ENDPOINT}/abc/clear-explored")
        assert r.status_code == 422

    def test_clear_all_explored_empty(self, client):
        r = client.post(f"{self.ENDPOINT}/clear-explored")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_clear_all_explored_with_worlds(self, client):
        client.post(self.ENDPOINT, json={"world_name": "CE1", "auto_research": False})
        client.post(self.ENDPOINT, json={"world_name": "CE2", "auto_research": False})
        r = client.post(f"{self.ENDPOINT}/clear-explored")
        assert r.json()["count"] == 2

    def test_research_unexplored_noop(self, client):
        r = client.post(f"{self.ENDPOINT}/research-unexplored")
        assert r.status_code == 200
        assert r.json()["status"] == "noop"


class TestFocusedSearch:
    ENDPOINT = "/api/focused-search"

    def test_missing_world_name(self, client):
        r = client.post(self.ENDPOINT, json={"feature": "magic"})
        assert r.status_code == 422

    def test_missing_feature(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "W"})
        assert r.status_code == 422

    def test_both_empty(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "", "feature": ""})
        assert r.status_code == 200

    def test_feature_xss(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "W", "feature": "<script>"})
        assert r.status_code == 200

    def test_feature_very_long(self, client):
        r = client.post(self.ENDPOINT, json={"world_name": "W", "feature": "A" * 10000})
        assert r.status_code == 200


class TestOrchestrate:
    ENDPOINT = "/api/orchestrate"

    def test_missing_worlds(self, client):
        r = client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_worlds_null(self, client):
        r = client.post(self.ENDPOINT, json={"worlds": None})
        assert r.status_code == 422

    def test_worlds_empty_list(self, client):
        r = client.post(self.ENDPOINT, json={"worlds": []})
        assert r.status_code == 400

    def test_worlds_with_empty_string(self, client):
        r = client.post(self.ENDPOINT, json={"worlds": [""]})
        assert r.status_code == 200

    def test_worlds_single(self, client):
        r = client.post(self.ENDPOINT, json={"worlds": ["Warhammer 40k"]})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "started"
        assert data["run_id"] is not None

    def test_worlds_not_a_list(self, client):
        r = client.post(self.ENDPOINT, json={"worlds": "single string"})
        assert r.status_code == 422


class TestAbort:
    ENDPOINT = "/api/abort"

    def test_missing_both_keys(self, client):
        r = client.post(self.ENDPOINT, json={})
        assert r.status_code == 400
        assert "runId" in r.json()["detail"]

    def test_run_id_empty(self, client):
        r = client.post("/api/abort", json={"run_id": ""})
        assert r.status_code == 400

    def test_run_id_valid(self, client):
        r = client.post(self.ENDPOINT, json={"run_id": "abc-123"})
        assert r.status_code == 200
        assert r.json()["status"] == "abort_requested"

    def test_runId_key(self, client):
        r = client.post(self.ENDPOINT, json={"runId": "some-run"})
        assert r.status_code == 200


class TestResults:
    def test_empty(self, client):
        r = client.get("/api/results")
        assert r.status_code == 200
        data = r.json()
        assert data["tier_system"] is None
        assert data["worlds"] == []

    def test_with_worlds(self, client):
        client.post("/api/worlds", json={"world_name": "ResultWorld", "auto_research": False})
        r = client.get("/api/results")
        data = r.json()
        names = [w["name"] for w in data["worlds"]]
        assert "ResultWorld" in names


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestSettingsGet:
    def test_empty(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        data = r.json()
        assert data["general_settings"] == {}
        assert data["providers"] == []
        assert data["agent_routes"] == []

    def test_with_data(self, client):
        client.post("/api/settings/general", json={"key": "test", "value": "val"})
        client.post("/api/providers", json={"name": "test-provider"})
        client.post("/api/agent-routes", json={"task_type": "TEST"})
        r = client.get("/api/settings")
        data = r.json()
        assert data["general_settings"].get("test") == "val"
        assert len(data["providers"]) >= 1
        assert len(data["agent_routes"]) >= 1


class TestModelStatus:
    def test_no_routes(self, client):
        r = client.get("/api/model-status")
        assert r.status_code == 200
        assert r.json()["routes"] == []


class TestResetAndClear:
    def test_clear_logs(self, client):
        r = client.post("/api/clear-logs")
        assert r.status_code == 200

    def test_reset_database(self, client):
        client.post("/api/worlds", json={"world_name": "ResetWorld", "auto_research": False})
        r = client.post("/api/reset-database")
        assert r.status_code == 200

    def test_reset_activity(self, client):
        r = client.post("/api/reset-activity")
        assert r.status_code == 200


class TestAgentActivity:
    def test_empty(self, client):
        r = client.get("/api/agent-activity")
        assert r.status_code == 200
        data = r.json()
        assert "active_runs" in data
        assert "logs" in data
