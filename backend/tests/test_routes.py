import pytest


class TestHealth:
    def test_health(self, api_client):
        r = api_client.get("/api/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestSettingsGeneral:
    ENDPOINT = "/api/settings/general"

    def test_missing_key(self, api_client):
        r = api_client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_key_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "", "value": "v"})
        assert r.status_code == 200

    def test_key_very_long(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "A" * 10000, "value": "v"})
        assert r.status_code == 200

    def test_key_with_xss(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"key": "<script>alert(1)</script>", "value": "x"}
        )
        assert r.status_code == 200

    def test_key_unicode(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "🔑-setting", "value": "emoji"})
        assert r.status_code == 200

    def test_value_null(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "nullable", "value": None})
        assert r.status_code == 200

    def test_value_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "empty-val", "value": ""})
        assert r.status_code == 200

    def test_value_very_long(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "long", "value": "A" * 100_000})
        assert r.status_code == 200

    def test_key_null(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": None, "value": "v"})
        assert r.status_code == 422

    def test_response_body(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"key": "mykey", "value": "myval"})
        data = r.json()
        assert data["status"] == "success"
        assert "mykey" in data["message"]


class TestWorlds:
    ENDPOINT = "/api/worlds/"
    SEED_COUNT = 1

    def test_get_empty(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_missing_world_name(self, api_client):
        r = api_client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_world_name_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"world_name": ""})
        assert r.status_code == 200

    def test_world_name_very_long(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"world_name": "A" * 500})
        assert r.status_code == 200

    def test_world_name_xss(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"world_name": "<script>alert('xss')</script>"}
        )
        assert r.status_code == 200

    def test_world_name_null(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"world_name": None})
        assert r.status_code == 422

    def test_duplicate_world_name(self, api_client):
        payload = {"world_name": "DuplicateWorld", "auto_research": False}
        api_client.post(self.ENDPOINT, json=payload)
        r = api_client.post(self.ENDPOINT, json=payload)
        assert r.status_code == 200

    def test_auto_research_false(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"world_name": "ManualWorld", "auto_research": False}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "created"

    def test_auto_research_null(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"world_name": "NullAuto", "auto_research": None}
        )
        assert r.status_code == 422

    def test_auto_research_not_bool(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"world_name": "BadAuto", "auto_research": "yes"}
        )
        assert r.status_code == 200

    def test_auto_research_omitted(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"world_name": "OmittedAuto"})
        assert r.status_code == 200
        assert r.json()["status"] == "queued"

    def test_get_after_create(self, api_client, _clean_db):
        api_client.post(
            self.ENDPOINT, json={"world_name": "GetTest", "auto_research": False}
        )
        r = api_client.get(self.ENDPOINT)
        data = r.json()
        assert r.status_code == 200
        assert isinstance(data, list)
        # Verify that the items in the list match UniverseResponse structure
        if data:
            w = data[0]
            assert "uuid" in w
            assert "slug" in w
            assert "name" in w
        names = [w["name"] for w in data]
        assert "GetTest" in names

    def test_get_by_uuid(self, api_client, _clean_db):
        api_client.post(
            self.ENDPOINT, json={"world_name": "UuidTest", "auto_research": False}
        )
        r_list = api_client.get(self.ENDPOINT)
        uuid_val = r_list.json()[0]["uuid"]

        r = api_client.get(f"/api/worlds/by-uuid/{uuid_val}")
        assert r.status_code == 200
        data = r.json()
        assert data["uuid"] == uuid_val
        assert data["name"] == "UuidTest"
        assert "slug" in data

    def test_reset_explored_nonexistent(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}99999/reset-explored")
        assert r.status_code == 404

    def test_reset_explored_negative(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}-1/reset-explored")
        assert r.status_code == 404

    def test_reset_explored_non_int(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}abc/reset-explored")
        assert r.status_code == 422

    def test_reset_all_explored_empty(self, api_client, _clean_db):
        r = api_client.post(f"{self.ENDPOINT}reset-all-explored")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_reset_all_explored_with_worlds(self, api_client):
        api_client.post(
            self.ENDPOINT, json={"world_name": "CE1", "auto_research": False}
        )
        api_client.post(
            self.ENDPOINT, json={"world_name": "CE2", "auto_research": False}
        )
        r = api_client.post(f"{self.ENDPOINT}reset-all-explored")
        assert r.json()["count"] == 0

    @pytest.mark.xfail(
        reason="seed worlds trigger pipeline, AGENT_TOOLS not in scope in test env"
    )
    def test_research_unexplored_noop(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}research-unexplored")
        assert r.status_code == 200
        assert r.json()["status"] == "noop"


class TestProviders:
    ENDPOINT = "/api/providers/"

    def test_missing_name(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"provider_type": "openai"})
        assert r.status_code == 422

    def test_name_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": ""})
        assert r.status_code == 200

    def test_name_xss(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": "<img onerror=alert(1)>"})
        assert r.status_code == 200

    def test_name_unicode(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": "提供者"})
        assert r.status_code == 200

    def test_name_very_long(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": "A" * 500})
        assert r.status_code == 200

    def test_id_zero(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"id": 0, "name": "zero-id"})
        assert r.status_code == 200
        data = r.json()
        assert data["provider"]["id"] is not None

    def test_id_negative(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"id": -1, "name": "neg-id"})
        assert r.status_code == 200

    def test_id_nonexistent(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"id": 9999, "name": "bad-id"})
        assert r.status_code == 200

    def test_provider_type_empty(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"name": "empty-type", "provider_type": ""}
        )
        assert r.status_code == 200

    def test_api_key_null(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": "null-key", "api_key": None})
        assert r.status_code == 200

    def test_base_url_malformed(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"name": "bad-url", "base_url": "not-a-url"}
        )
        assert r.status_code == 200

    def test_models_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": "no-models", "models": ""})
        assert r.status_code == 200

    def test_models_csv(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"name": "csv-models", "models": "gpt-4,gpt-3.5"}
        )
        assert r.status_code == 200

    def test_models_with_spaces(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"name": "space-models", "models": "gpt-4, gpt-3.5"}
        )
        assert r.status_code == 200

    def test_duplicate_name(self, api_client):
        r1 = api_client.post(self.ENDPOINT, json={"name": "dup-prove"})
        assert r1.status_code == 200
        r2 = api_client.post(
            self.ENDPOINT, json={"name": "dup-prove", "provider_type": "anthropic"}
        )
        assert r2.status_code == 200

    def test_minimal_payload(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"name": "minimal"})
        assert r.status_code == 200

    def test_get_empty(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_after_create(self, api_client):
        api_client.post(
            self.ENDPOINT, json={"name": "get-test", "provider_type": "openai"}
        )
        r = api_client.get(self.ENDPOINT)
        data = r.json()
        assert len(data) >= 1
        assert any(p["name"] == "get-test" for p in data)

    def test_get_provider_models_nonexistent(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}9999/models")
        assert r.status_code == 404

    def test_get_provider_models_negative(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}-1/models")
        assert r.status_code == 404

    def test_get_provider_models_non_int(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}abc/models")
        assert r.status_code == 422


class TestAgentRoutes:
    ENDPOINT = "/api/settings/agent-routes"

    def test_missing_task_type(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"provider_id": 1})
        assert r.status_code == 422

    def test_task_type_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"task_type": ""})
        assert r.status_code == 200

    def test_task_type_unknown(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"task_type": "NONEXISTENT"})
        assert r.status_code == 200

    def test_task_type_very_long(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"task_type": "A" * 500})
        assert r.status_code == 200

    def test_delete_provider(self, api_client):
        r = api_client.post(
            f"{TestProviders.ENDPOINT}",
            json={"name": "delete-me", "provider_type": "openai"},
        )
        data = r.json()
        pid = data["provider"]["id"]
        dr = api_client.delete(f"{TestProviders.ENDPOINT.rstrip('/')}/{pid}")
        assert dr.status_code == 200
        get_r = api_client.get(TestProviders.ENDPOINT)
        assert not any(p["id"] == pid for p in get_r.json())

    def test_delete_provider_not_found(self, api_client):
        dr = api_client.delete(f"{TestProviders.ENDPOINT}/99999")
        assert dr.status_code == 404

    def test_provider_id_null(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"task_type": "NULL_PROV", "provider_id": None}
        )
        assert r.status_code == 200

    def test_provider_id_zero(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"task_type": "ZERO_PROV", "provider_id": 0}
        )
        assert r.status_code == 422

    def test_provider_id_nonexistent(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"task_type": "BAD_FK", "provider_id": 9999}
        )
        assert r.status_code == 422

    def test_models_null(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"task_type": "NULL_MODELS", "models": None}
        )
        assert r.status_code == 200

    def test_models_empty(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"task_type": "EMPTY_MODELS", "models": ""}
        )
        assert r.status_code == 200

    def test_duplicate_task_type_upsert(self, api_client):
        api_client.post(self.ENDPOINT, json={"task_type": "UPSERT", "models": "v1"})
        r = api_client.post(self.ENDPOINT, json={"task_type": "UPSERT", "models": "v2"})
        assert r.status_code == 200

    def test_get_empty(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert len(r.json()) >= 1
        assert any(route["task_type"] == "DEFAULT" for route in r.json())

    def test_get_after_create(self, api_client):
        api_client.post(self.ENDPOINT, json={"task_type": "GET_TEST"})
        r = api_client.get(self.ENDPOINT)
        assert any(route["task_type"] == "GET_TEST" for route in r.json())


class TestFocusedSearch:
    ENDPOINT = "/api/runs/focused-search"

    def test_success(self, api_client):
        payload = {
            "universe_uuids": ["some-uuid-1", "some-uuid-2"],
            "features": ["Feature1", "Feature2"],
        }
        r = api_client.post(self.ENDPOINT, json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "started"
        assert data["run_id"] is not None
        assert data["uuids"] == payload["universe_uuids"]
        assert data["features"] == payload["features"]


    def test_missing_worlds(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"features": ["magic"]})
        assert r.status_code == 422

    def test_missing_features(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"worlds": ["W"]})
        assert r.status_code == 422

    def test_both_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"universe_uuids": [], "features": []})
        assert r.status_code == 200
        assert r.json()["status"] == "started"


    def test_worlds_not_a_list(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"worlds": "SingleWorld", "features": ["f"]}
        )
        assert r.status_code == 422

    def test_features_not_a_list(self, api_client):
        r = api_client.post(
            self.ENDPOINT, json={"worlds": ["W"], "features": "SingleFeature"}
        )
        assert r.status_code == 422


class TestOrchestrate:
    ENDPOINT = "/api/runs/workflow"

    def test_missing_worlds(self, api_client):
        r = api_client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_worlds_null(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"worlds": None})
        assert r.status_code == 422

    def test_worlds_empty_list(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"universe_uuids": []})
        assert r.status_code == 400


    def test_worlds_with_empty_string(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"universe_uuids": [""]})
        assert r.status_code == 200


    def test_worlds_single(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"universe_uuids": ["Warhammer 40k"]})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "started"
        assert data["run_id"] is not None


    def test_worlds_not_a_list(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"worlds": "single string"})
        assert r.status_code == 422


class TestAbort:
    ENDPOINT = "/api/runs/abort"

    def test_missing_both_keys(self, api_client):
        r = api_client.post(self.ENDPOINT, json={})
        assert r.status_code == 422

    def test_run_id_empty(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"run_id": ""})
        assert r.status_code == 422

    def test_run_id_valid(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"run_id": "abc-123"})
        assert r.status_code == 200
        assert r.json()["status"] == "abort_requested"

    def test_run_id_key(self, api_client):
        r = api_client.post(self.ENDPOINT, json={"runId": "some-run"})
        assert r.status_code == 200


class TestResults:
    ENDPOINT = "/api/research/results"

    def test_empty(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert data["tier_system"] is None
        assert len(data["worlds"]) >= 1

    def test_with_worlds(self, api_client):
        api_client.post(
            "/api/worlds/", json={"world_name": "ResultWorld", "auto_research": False}
        )
        r = api_client.get(self.ENDPOINT)
        data = r.json()
        names = [w["name"] for w in data["worlds"]]
        assert "ResultWorld" in names


class TestSettingsGet:
    ENDPOINT = "/api/settings/"

    def test_empty(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data["general_settings"], dict)
        assert isinstance(data["providers"], list)
        assert len(data["agent_routes"]) >= 1
        assert any(route["task_type"] == "DEFAULT" for route in data["agent_routes"])

    def test_with_data(self, api_client):
        api_client.post("/api/settings/general", json={"key": "test", "value": "val"})
        api_client.post("/api/providers", json={"name": "test-provider"})
        api_client.post("/api/settings/agent-routes", json={"task_type": "TEST"})
        r = api_client.get(self.ENDPOINT)
        data = r.json()
        assert data["general_settings"].get("test") == "val"
        assert len(data["providers"]) >= 1
        assert len(data["agent_routes"]) >= 1


class TestModelStatus:
    def test_no_routes(self, api_client):
        r = api_client.get("/api/settings/model-status")
        assert r.status_code == 200
        data = r.json()
        assert "initialized" in data
        assert "routes" in data
        assert isinstance(data["routes"], list)
        if data["routes"]:
            route = data["routes"][0]
            assert "task_type" in route
            assert "configured" in route
            assert "provider" in route
            assert "models" in route


class TestAgentActivity:
    def test_empty(self, api_client):
        r = api_client.get("/api/runs/agent-activity")
        assert r.status_code == 200
        data = r.json()
        assert "active_runs" in data
        assert "logs" in data
        assert isinstance(data["active_runs"], list)
        assert isinstance(data["logs"], list)
        if data["logs"]:
            log = data["logs"][0]
            assert "run_id" in log
            assert "node_name" in log
            assert "status" in log
            assert "created_at" in log


class TestResetAndClear:
    def test_clear_logs(self, api_client):
        r = api_client.post("/api/worlds/clear-logs")
        assert r.status_code == 200

    def test_reset_database(self, api_client):
        api_client.post(
            "/api/worlds", json={"world_name": "ResetWorld", "auto_research": False}
        )
        r = api_client.post("/api/worlds/reset-database")
        assert r.status_code == 200

    def test_reset_activity(self, api_client):
        r = api_client.post("/api/runs/reset-activity")
        assert r.status_code == 200


class TestResearch:
    def test_unconfirmed_claims(self, api_client):
        r = api_client.get("/api/research/claims/unconfirmed")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            claim = data[0]
            assert "subject" in claim
            assert "predicate" in claim
            assert "object_val" in claim
            assert "universe_name" in claim

    def test_results(self, api_client):
        r = api_client.get("/api/research/results")
        assert r.status_code == 200
        data = r.json()
        assert "tier_system" in data
        assert "worlds" in data
        assert "anomalies" in data
        assert isinstance(data["worlds"], list)
        if data["worlds"]:
            w = data["worlds"][0]
            assert "id" in w
            assert "name" in w
            assert "tier" in w

    def test_theories(self, api_client):
        r = api_client.get("/api/research/theories")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            t = data[0]
            assert "id" in t
            assert "theory" in t
            assert "universe_id" in t
