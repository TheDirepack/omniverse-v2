from app.agents.prompts import (
    get_architect_prompt,
    get_critic_prompt,
    get_extrapolation_prompt,
    get_researcher_prompt,
    get_stability_prompt,
    get_theory_auditor_prompt,
)


class TestExtractionPrompt:
    def test_basic(self):
        result = get_researcher_prompt("Marvel", "Magic System, Technology")
        assert "system" in result
        assert "user" in result
        assert "Marvel" in result["system"]
        assert "Marvel" in result["user"]

    def test_empty_entity(self):
        result = get_researcher_prompt("", "")
        assert "system" in result
        assert "user" in result

    def test_with_focus(self):
        result = get_researcher_prompt(
            "DC", "Speed Force", focus="Speed Force abilities"
        )
        assert "FOCUSED FEATURE TARGET" in result["system"]
        assert "Speed Force" in result["system"]

    def test_empty_focus(self):
        result = get_researcher_prompt("Test", "req", focus="")
        assert "FOCUSED FEATURE TARGET" not in result["system"]

    def test_requirements_in_system(self):
        result = get_researcher_prompt("W", "Custom Requirement")
        assert "Custom Requirement" in result["system"]

    def test_prohibits_scaling(self):
        result = get_researcher_prompt("Marvel", "req")
        assert "PROHIBITED" in result["system"]
        assert "power-scaling" in result["system"]
        assert "feat analysis" in result["system"]

    def test_enforces_staging_reframing(self):
        result = get_researcher_prompt("Marvel", "req")
        assert "RESEARCH NOTES (Staging DB)" in result["system"]
        assert "persistent research notes" in result["system"]

    def test_without_previous_dataset_initial_mode(self):
        """Test the original bug: calling get_researcher_prompt without previous_dataset should work (initial research mode)."""
        # This used to raise UnboundLocalError: cannot access local variable 'system_parts' 
        # because it was only defined inside the if block
        result = get_researcher_prompt("Test World", "Test Requirement")
        assert "system" in result
        assert "user" in result
        assert "INITIAL RESEARCH" in result["system"]
        assert "PATCH & REFINE MODE" not in result["system"]
        assert "PREVIOUS DATASET" not in result["system"]
        
        # Verify system_parts list was constructed properly
        assert "### ROLE" in result["system"]
        assert "CORE DIRECTIVES" in result["system"]
        assert "RESEARCH PHILOSOPHY & WORKFLOW" in result["system"]

    def test_with_workspace_index(self):
        """Test that workspace_index is included in the prompt."""
        workspace_idx = "RESEARCH NOTES:\n[1] Test Note (Status: OPEN, Priority: 5)"
        result = get_researcher_prompt("Test World", "Test", workspace_index=workspace_idx)
        assert "RESEARCH WORKSPACE (Working Memory)" in result["system"]
        assert "Test Note" in result["system"]

    def test_with_notebook_source_timeline_indices(self):
        """Test that individual indices are shown when workspace_index is None."""
        result = get_researcher_prompt(
            "Test World", "Test",
            notebook_index="[1] Note (Status: OPEN)",
            source_index="[1] Source (Reliability: High)",
            timeline_index="[1] Event (Era: Ancient)"
        )
        assert "NOTEBOOK INDEX" in result["system"]
        assert "SOURCE LIBRARY INDEX" in result["system"]
        assert "TIMELINE INDEX" in result["system"]
        assert "[1] Note" in result["system"]
        assert "[1] Source" in result["system"]
        assert "[1] Event" in result["system"]

    def test_focus_block_inclusion(self):
        """Test that focus_block is included when focus is provided."""
        result = get_researcher_prompt("Test World", "Test", focus="Magic System")
        assert "FOCUSED FEATURE TARGET" in result["system"]
        assert "Magic System" in result["system"]
        assert "prove existence" in result["system"]

    def test_focus_exclusion(self):
        """Test that focus_block is excluded when focus is empty."""
        result = get_researcher_prompt("Test World", "Test", focus="")
        assert "FOCUSED FEATURE TARGET" not in result["system"]

    def test_multiple_requirements(self):
        """Test that multiple requirements are included."""
        result = get_researcher_prompt("Test World", "Magic System, Technology, History")
        assert "Magic System" in result["system"]
        assert "Technology" in result["system"]
        assert "History" in result["system"]
        assert "Requirements: Magic System, Technology, History" in result["system"]

    def test_schema_inclusion(self):
        """Test that RESEARCH_SCHEMA is included in the output."""
        result = get_researcher_prompt("Test World", "Test")
        assert "matching this schema" in result["system"]
        assert "OUTPUT FORMAT" in result["system"]

    def test_no_invented_data_directive(self):
        """Test that the no invented data directive is present."""
        result = get_researcher_prompt("Test World", "Test")
        assert "No invented data" in result["system"]
        assert "PROHIBITED" in result["system"]

    def test_technical_rigor_directive(self):
        """Test that technical rigor directives are present."""
        result = get_researcher_prompt("Test World", "Test")
        assert "TECHNICAL RIGOR" in result["system"]
        assert "NO HEADCANON" in result["system"]
        assert "PRECISE GROUNDING" in result["system"]

    def test_documentation_tools_mentioned(self):
        """Test that documentation tools are mentioned in the prompt."""
        result = get_researcher_prompt("Test World", "Test")
        assert "`saveNotebookEntry`" in result["system"]
        assert "`manage_source`" in result["system"]
        assert "`record_timeline_event`" in result["system"]

    def test_all_modes(self):
        """Test different mode_block values."""
        # Initial research mode
        result = get_researcher_prompt("World", "req")
        assert "INITIAL RESEARCH" in result["system"]
        
        # Patch mode with previous dataset
        result = get_researcher_prompt("World", "req", previous_dataset="old")
        assert "PATCH & REFINE MODE" in result["system"]
        assert "PREVIOUS DATASET" in result["system"]

    def test_empty_all_params(self):
        """Test with all optional parameters empty."""
        result = get_researcher_prompt("", "", focus="", previous_dataset="")
        assert "system" in result
        assert "user" in result
        # Should still generate valid prompt even with empty inputs

    def test_multiverse_context(self):
        """Test that multiverse context is included when provided."""
        result = get_researcher_prompt(
            "World", "req",
            multiverse_leads="[1] Parent universe data",
            multiverse_kg="KG: {\"lead\": \"test\"}"
        )
        assert "MULTIVERSE LEADS (Parent/Children Universes)" in result["system"]
        assert "LEADS:" in result["system"]
        assert "KNOWLEDGE GRAPH:" in result["system"]

    def test_verified_claims_context(self):
        """Test that verified claims context is included when provided."""
        verified = "Verified: Character X is Y"
        result = get_researcher_prompt("World", "req", verified_claims=verified)
        assert "VERIFIED KNOWLEDGE BASE" in result["system"]
        assert "already confirmed" in result["system"]

    def test_existing_knowledge_graph(self):
        """Test that existing knowledge graph is included when provided."""
        graph = '{"Entity": {"fact": "test"}}'
        result = get_researcher_prompt("World", "req", knowledge_graph=graph)
        assert "EXISTING KNOWLEDGE GRAPH" in result["system"]
        assert graph in result["system"]


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

    def test_prohibits_scaling(self):
        result = get_critic_prompt("data", "crit")
        assert "PROHIBITED" in result["system"]
        assert "power-scaling" in result["system"]
        assert "relative strength comparisons" in result["system"]


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
