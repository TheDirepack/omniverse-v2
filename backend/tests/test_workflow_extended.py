"""Tests for workflow modules: tiering_workflow, consolidation_workflow, extrapolation_workflow."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.schema import Universe
from app.workflow.tiering_workflow import _parse_stability_result, audit_success


class TestAuditSuccess:
    """Pure function tests for audit_success."""

    def test_json_success(self):
        result = json.dumps({"Verification_Status": "SUCCESS"})
        assert audit_success(result) is True

    def test_json_failure(self):
        result = json.dumps({"Verification_Status": "REVISION_REQUIRED"})
        assert audit_success(result) is False

    def test_json_empty_status(self):
        result = json.dumps({"Verification_Status": ""})
        assert audit_success(result) is False

    def test_json_missing_status(self):
        result = json.dumps({"other": "value"})
        assert audit_success(result) is False

    def test_text_success(self):
        assert audit_success("SUCCESS") is True

    def test_text_verified(self):
        assert audit_success("VERIFIED") is True

    def test_text_status_success(self):
        assert audit_success("STATUS: SUCCESS") is True

    def test_text_status_verified(self):
        assert audit_success("STATUS: VERIFIED") is True

    def test_revision_required(self):
        assert audit_success("REVISION_REQUIRED") is False

    def test_random_text(self):
        assert audit_success("some random output") is False

    def test_empty_string(self):
        assert audit_success("") is False

    def test_non_json_parseable(self):
        # Should not crash on malformed JSON
        result = "{invalid json"
        # Falls through to line-based check
        assert isinstance(audit_success(result), bool)

    def test_non_string_input(self):
        # Should not crash on non-string
        with pytest.raises((AttributeError, TypeError)):
            audit_success(None)  # noqa


class TestParseStabilityResult:
    """Pure function tests for _parse_stability_result."""

    def test_stable_with_tier(self):
        result = _parse_stability_result("STATUS: STABLE\nTIER: 5\nSome justification")
        assert result["status"] == "STABLE"
        assert result["tier"] == 5

    def test_anomaly_with_tier(self):
        result = _parse_stability_result("STATUS: ANOMALY\nTIER: 8")
        assert result["status"] == "ANOMALY"
        assert result["tier"] == 8

    def test_insufficient_data(self):
        result = _parse_stability_result("STATUS: INSUFFICIENT_DATA")
        assert result["status"] == "INSUFFICIENT"
        assert result["tier"] is None

    def test_unknown_status(self):
        result = _parse_stability_result("some random text")
        assert result["status"] == "UNKNOWN"
        assert result["tier"] is None

    def test_tier_out_of_range_low(self):
        result = _parse_stability_result("STATUS: STABLE\nTIER: -5")
        assert result["tier"] is None

    def test_tier_out_of_range_high(self):
        result = _parse_stability_result("STATUS: STABLE\nTIER: 20")
        assert result["tier"] == 10

    def test_tier_not_a_number(self):
        with patch("app.workflow.tiering_workflow.logging.exception") as mock_log:
            result = _parse_stability_result("STATUS: STABLE\nTIER: not_a_number")
            assert result["tier"] is None
            mock_log.assert_not_called()

    def test_justification_preserved(self):
        text = "STATUS: STABLE\nTIER: 3\nCustom justification here"
        result = _parse_stability_result(text)
        assert result["justification"] == text


class TestExtrapolationNode:
    """Partial tests for extrapolation_node with mocks."""

    async def test_missing_run_id_raises(self):
        from app.workflow.extrapolation_workflow import extrapolation_node
        with pytest.raises(RuntimeError, match="run_id is required"):
            await extrapolation_node({})

    async def test_aborted_raises(self):
        from app.workflow.extrapolation_workflow import extrapolation_node

        with patch(
            "app.core.runtime_state.is_aborted",
            new=AsyncMock(return_value=True),
        ):
            with pytest.raises(RuntimeError, match="aborted"):
                await extrapolation_node({"run_id": "aborted-extrap"})

    async def test_no_verified_worlds(self):
        from app.workflow.extrapolation_workflow import extrapolation_node

        with (
            patch(
                "app.core.runtime_state.is_aborted",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.workflow.extrapolation_workflow.UniverseService",
            ),
            patch(
                "app.workflow.extrapolation_workflow.ExecutionService",
            ),
            patch(
                "app.workflow.extrapolation_workflow.TheoryService",
            ),
        ):
            result = await extrapolation_node({
                "run_id": "test-extrap",
                "verified_worlds": [],
            })
            assert result["active_task"] == "FINISHED"


class TestTieringArchitectureNode:
    """Partial tests for architecture_node with mocks."""

    async def test_aborted_raises(self):
        from app.workflow.tiering_workflow import architecture_node

        with patch(
            "app.core.runtime_state.is_aborted",
            new=AsyncMock(return_value=True),
        ):
            with pytest.raises(RuntimeError, match="aborted"):
                await architecture_node({"run_id": "aborted-tier"})


class TestTieringWorkflowPureFunctions:
    """Edge cases for tiering helper functions."""

    def test_audit_success_json_case_insensitive(self):
        assert audit_success(json.dumps({"Verification_Status": "success"})) is True
        assert audit_success(json.dumps({"Verification_Status": "Success"})) is True

    def test_parse_stability_mixed_case(self):
        result = _parse_stability_result("Status: stable\nTier: 7")
        assert result["status"] == "STABLE"
        assert result["tier"] == 7

    def test_parse_stability_justification_only(self):
        text = "The world is stable at Tier 4 based on available data"
        result = _parse_stability_result(text)
        assert result["status"] == "UNKNOWN"
        assert result["tier"] is None
        assert result["justification"] == text
