import pytest
from app.core.templates import compute_resolved_fallback


class TestComputeResolvedFallback:
    def test_empty_routes_and_providers(self):
        assert compute_resolved_fallback([], []) == []

    def test_route_without_matching_provider_skipped(self):
        routes = [{"provider_id": 1, "models": "gpt-4"}]
        providers = [{"id": 2, "name": "Other"}]
        assert compute_resolved_fallback(routes, providers) == []

    def test_route_with_provider_and_models_from_route(self):
        routes = [{"provider_id": 1, "models": "gpt-4, gpt-3.5"}]
        providers = [{"id": 1, "name": "OpenAI"}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 2
        assert result[0]["model"] == "gpt-4"
        assert result[0]["provider"] == "OpenAI"
        assert result[1]["model"] == "gpt-3.5"

    def test_models_from_provider_when_route_has_no_models(self):
        routes = [{"provider_id": 1, "models": ""}]
        providers = [{"id": 1, "name": "Anthropic", "models": "claude-3"}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 1
        assert result[0]["model"] == "claude-3"

    def test_models_fallback_when_both_empty(self):
        routes = [{"provider_id": 1}]
        providers = [{"id": 1, "name": "Empty", "models": ""}]
        assert compute_resolved_fallback(routes, providers) == []

    def test_multiple_keys_generate_separate_rows(self):
        routes = [{"provider_id": 1, "models": "gpt-4"}]
        providers = [{"id": 1, "name": "MultiKey", "keys": [{"k": "v1"}, {"k": "v2"}]}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 2
        assert result[0]["key_label"] == "Key 1"
        assert result[1]["key_label"] == "Key 2"

    def test_single_key_no_keys_label(self):
        routes = [{"provider_id": 1, "models": "gpt-4"}]
        providers = [{"id": 1, "name": "NoKeys"}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 1
        assert result[0]["key_label"] == "No Key"

    def test_deduplication_skips_duplicate_combinations(self):
        routes = [
            {"provider_id": 1, "models": "gpt-4", "priority": 1},
            {"provider_id": 1, "models": "gpt-4", "priority": 2},
        ]
        providers = [{"id": 1, "name": "Dedup"}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 1

    def test_routes_sorted_by_priority(self):
        routes = [
            {"provider_id": 1, "models": "model-b", "priority": 10},
            {"provider_id": 1, "models": "model-a", "priority": 1},
        ]
        providers = [{"id": 1, "name": "Sorted"}]
        result = compute_resolved_fallback(routes, providers)
        assert result[0]["model"] == "model-a"
        assert result[1]["model"] == "model-b"

    def test_none_priority_treated_as_zero(self):
        routes = [
            {"provider_id": 1, "models": "model-a", "priority": 5},
            {"provider_id": 1, "models": "model-b", "priority": None},
        ]
        providers = [{"id": 1, "name": "NonePri"}]
        result = compute_resolved_fallback(routes, providers)
        assert result[0]["model"] == "model-b"
        assert result[1]["model"] == "model-a"

    def test_no_keys_in_provider_but_keys_field_present(self):
        routes = [{"provider_id": 1, "models": "gpt-4"}]
        providers = [{"id": 1, "name": "EmptyKeys", "keys": []}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 1

    def test_mixed_matching_and_non_matching_routes(self):
        routes = [
            {"provider_id": 1, "models": "gpt-4"},
            {"provider_id": 99, "models": "nonexistent"},
        ]
        providers = [{"id": 1, "name": "Only"}]
        result = compute_resolved_fallback(routes, providers)
        assert len(result) == 1
        assert result[0]["model"] == "gpt-4"
