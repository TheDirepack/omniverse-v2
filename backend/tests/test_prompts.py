import pytest
from app.agents.prompts import (
    get_extraction_prompt,
    get_critic_prompt,
    get_synthesis_prompt,
    get_architect_prompt,
    get_stability_prompt,
    get_extrapolation_prompt,
    get_theory_auditor_prompt,
)


class TestExtractionPrompt:
    def test_basic(self):
        result = get_extraction_prompt("Marvel", "Magic System, Technology")
        assert "system" in result
        assert "user" in result
        assert "Marvel" in result["system"]
        assert "Marvel" in result["user"]

    def test_empty_entity(self):
        result = get_extraction_prompt("", "")
        assert "system" in result
        assert "user" in result

    def test_with_focus(self):
        result = get_extraction_prompt("DC", "Speed Force", focus="Speed Force abilities")
        assert "FOCUSED FEATURE TARGET" in result["system"]
        assert "Speed Force" in result["system"]

    def test_empty_focus(self):
        result = get_extraction_prompt("Test", "req", focus="")
        assert "FOCUSED FEATURE TARGET" not in result["system"]

    def test_requirements_in_system(self):
        result = get_extraction_prompt("W", "Custom Requirement")
        assert "Custom Requirement" in result["system"]


class TestCriticPrompt:
    def test_basic(self):
        result = get_critic_prompt("some data", "accuracy check")
        assert "system" in result
        assert "user" in result
        assert "some data" in result["user"]
        assert "accuracy check" in result["system"]

    def test_empty_data(self):
        result = get_critic_prompt("", "")
        assert "system" in result
        assert "user" in result


class TestSynthesisPrompt:
    def test_single_report(self):
        result = get_synthesis_prompt(["Report 1"])
        assert "Report 1" in result["user"]

    def test_multiple_reports(self):
        result = get_synthesis_prompt(["R1", "R2"])
        assert "R1" in result["user"]
        assert "R2" in result["user"]

    def test_empty_list(self):
        result = get_synthesis_prompt([])
        assert "user" in result


class TestArchitectPrompt:
    def test_basic(self):
        result = get_architect_prompt("dataset here", ["anomaly1"])
        assert "dataset here" in result["user"]
        assert "anomaly1" in result["user"]

    def test_empty_dataset(self):
        result = get_architect_prompt("", [])
        assert "user" in result

    def test_multiple_anomalies(self):
        result = get_architect_prompt("d", ["a1", "a2"])
        assert "a1" in result["user"]
        assert "a2" in result["user"]


class TestStabilityPrompt:
    def test_basic(self):
        result = get_stability_prompt("world data", "tier system")
        assert "world data" in result["user"]
        assert "tier system" in result["user"]

    def test_empty(self):
        result = get_stability_prompt("", "")
        assert "user" in result


class TestExtrapolationPrompt:
    def test_basic(self):
        result = get_extrapolation_prompt("Marvel", "data", "DC data")
        assert "Marvel" in result["user"]
        assert "DC data" in result["user"]

    def test_empty(self):
        result = get_extrapolation_prompt("", "", "")
        assert "user" in result


class TestTheoryAuditorPrompt:
    def test_basic(self):
        result = get_theory_auditor_prompt("theory text")
        assert "theory text" in result["user"]

    def test_empty(self):
        result = get_theory_auditor_prompt("")
        assert "user" in result
