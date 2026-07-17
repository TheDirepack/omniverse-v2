from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.domain import ResearchTarget
from app.db.schema import Universe
from app.research.researcher import (
    UniverseNotFoundError,
    WorldResearcher,
)


@pytest.fixture
def mock_target():
    return ResearchTarget(uuid="test-uuid", name="TestUniverse")

@pytest.fixture
def researcher(mock_target):
    return WorldResearcher(target=mock_target, run_id="test-run-id")

@pytest.mark.asyncio
async def test_research_universe_not_found(researcher):
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = None

    with pytest.raises(UniverseNotFoundError):
        await researcher.research()

@pytest.mark.asyncio
async def test_gather_universe_context_basic(researcher):
    # Mock universe
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")

    # Mock services
    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = [
        {"subject": "A", "predicate": "is", "object": "B", "reference": "ref1", "support": 1}
    ]
    researcher.retriever.get_universe_knowledge_graph.return_value = {"nodes": [], "edges": []}

    researcher.uni_service = MagicMock()
    researcher.uni_service.get_children.return_value = []

    context = await researcher._gather_universe_context(universe)

    assert "(A --is--> B) | ref: ref1" in context["verified_claims"]
    assert "nodes" in context["knowledge_graph"]
    assert context["multiverse_leads"] == ""
    assert context["multiverse_kg"] == ""

@pytest.mark.asyncio
async def test_gather_universe_context_with_relations(researcher):
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid", parent_id=10)

    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}

    researcher.uni_service = MagicMock()
    # Mock child universe
    child = Universe(id=2, name="ChildUniverse")
    researcher.uni_service.get_children.return_value = [child]

    # Mock get_universe_by_id for parent and child
    def get_uni(uid):
        if uid == 10: return Universe(id=10, name="ParentUniverse")
        if uid == 2: return Universe(id=2, name="ChildUniverse")
        return None
    researcher.uni_service.get_universe_by_id.side_effect = get_uni

    # Mock retriever for related universes
    def get_claims(uid):
        if uid == 10: return [{"subject": "P", "predicate": "is", "object": "Q", "reference": "p_ref", "support": 1}]
        if uid == 2: return [{"subject": "C", "predicate": "is", "object": "D", "reference": "c_ref", "support": 1}]
        return []
    researcher.retriever.get_semantic_claims.side_effect = get_claims

    def get_kg(uid):
        return {"kg": uid}
    researcher.retriever.get_universe_knowledge_graph.side_effect = get_kg

    context = await researcher._gather_universe_context(universe)

    assert "--- ParentUniverse ---" in context["multiverse_leads"]
    assert "(P --is--> Q) | ref: p_ref" in context["multiverse_leads"]
    assert "--- ChildUniverse ---" in context["multiverse_leads"]
    assert "(C --is--> D) | ref: c_ref" in context["multiverse_leads"]
    assert '"kg": 10' in context["multiverse_kg"]
    assert '"kg": 2' in context["multiverse_kg"]

def test_handle_audit_failure_valid_json(researcher):
    critique = '{"Correction_Queue": [{"Error_Type": "Logic", "Issue": "Wrong date", "Required_Fix": "Change to 1990"}]}'
    feedback = researcher._handle_audit_failure(critique)
    assert "[Logic] Wrong date -> Fix: Change to 1990" in feedback

def test_handle_audit_failure_invalid_json(researcher):
    critique = "This is just a string critique"
    feedback = researcher._handle_audit_failure(critique)
    assert feedback == critique

def test_handle_audit_failure_empty_queue(researcher):
    critique = '{"Correction_Queue": []}'
    feedback = researcher._handle_audit_failure(critique)
    assert feedback == "General improvements needed."

@pytest.mark.asyncio
async def test_research_happy_path(researcher):
    # Mock universe
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = universe

    researcher.tier_service = MagicMock()
    researcher.settings_service = MagicMock()
    researcher.settings_service.get_setting.return_value = MagicMock(value="1")

    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}

    researcher.uni_service.get_children.return_value = []

    researcher.workspace_service = MagicMock()
    researcher.exec_service = MagicMock()

    # Mock run_agent
    with patch("app.research.researcher.run_agent", new_callable=AsyncMock) as mock_run:
        # Researcher turn returns a valid JSON result
        mock_run.side_effect = [
            (True, '{"Verified_Data": "some data"}', [], "system_prompt"), # Researcher
            (True, '{"Verification_Status": "SUCCESS"}', [], "audit_prompt"), # Auditor
        ]

        # Mock audit_success to return True
        with patch("app.research.researcher.audit_success", return_value=True):
            result = await researcher.research()

            assert result["status"] == "VERIFIED"
            assert result["summary"] == '{"Verified_Data": "some data"}'
            assert mock_run.call_count == 2

@pytest.mark.asyncio
async def test_research_json_decode_failure(researcher):
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = universe
    researcher.tier_service = MagicMock()
    researcher.settings_service = MagicMock()
    researcher.settings_service.get_setting.return_value = MagicMock(value="2")
    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}
    researcher.uni_service.get_children.return_value = []
    researcher.workspace_service = MagicMock()
    researcher.exec_service = MagicMock()

    with patch("app.research.researcher.run_agent", new_callable=AsyncMock) as mock_run:
        # 1st iteration: Invalid JSON
        # 2nd iteration: Valid JSON
        mock_run.side_effect = [
            (True, "NOT JSON", [], "p1"),
            (True, '{"Verified_Data": "ok"}', [], "p2"),
            (True, '{"Verification_Status": "SUCCESS"}', [], "p3"),
        ]

        with patch("app.research.researcher.audit_success", return_value=True):
            result = await researcher.research()
            assert result["status"] == "VERIFIED"
            # Total calls: 1 (invalid JSON) + 1 (valid JSON) + 1 (audit) = 3
            assert mock_run.call_count == 3

@pytest.mark.asyncio
async def test_research_audit_failure(researcher):
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = universe
    researcher.tier_service = MagicMock()
    researcher.settings_service = MagicMock()
    researcher.settings_service.get_setting.return_value = MagicMock(value="2")
    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}
    researcher.uni_service.get_children.return_value = []
    researcher.workspace_service = MagicMock()
    researcher.exec_service = MagicMock()

    with patch("app.research.researcher.run_agent", new_callable=AsyncMock) as mock_run:
        # Iteration 1: Researcher OK, Auditor Fails
        # Iteration 2: Researcher OK, Auditor OK
        mock_run.side_effect = [
            (True, '{"data": "v1"}', [], "p1"),
            (True, '{"Verification_Status": "REVISION"}', [], "p2"),
            (True, '{"data": "v2"}', [], "p3"),
            (True, '{"Verification_Status": "SUCCESS"}', [], "p4"),
        ]

        # Audit success returns False then True
        with patch("app.research.researcher.audit_success", side_effect=[False, True]):
            result = await researcher.research()
            assert result["status"] == "VERIFIED"
            assert result["summary"] == '{"data": "v2"}'
            assert mock_run.call_count == 4

@pytest.mark.asyncio
async def test_research_max_iterations(researcher):
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = universe
    researcher.tier_service = MagicMock()
    researcher.settings_service = MagicMock()
    researcher.settings_service.get_setting.return_value = MagicMock(value="1")
    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}
    researcher.uni_service.get_children.return_value = []
    researcher.workspace_service = MagicMock()
    researcher.exec_service = MagicMock()

    with patch("app.research.researcher.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (True, '{"data": "v1"}', [], "p1")

        with patch("app.research.researcher.audit_success", return_value=False):
            result = await researcher.research()
            assert result["status"] == "PARTIAL"
            assert result["summary"] == '{"data": "v1"}'

@pytest.mark.asyncio
async def test_research_aborted(researcher):
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = universe
    researcher.tier_service = MagicMock()
    researcher.settings_service = MagicMock()
    researcher.settings_service.get_setting.return_value = MagicMock(value="2")
    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}
    researcher.uni_service.get_children.return_value = []
    researcher.workspace_service = MagicMock()
    researcher.exec_service = MagicMock()

    with patch("app.research.researcher.run_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (True, '{"data": "v1"}', [], "p1")

        with patch("app.research.researcher.is_aborted", return_value=True):
            with pytest.raises(RuntimeError, match="Aborted"):
                await researcher.research()

@pytest.mark.asyncio
async def test_research_exception_logging(researcher):
    universe = Universe(id=1, name="TestUniverse", uuid="test-uuid")
    researcher.uni_service = MagicMock()
    researcher.uni_service.get_universe_by_uuid.return_value = universe
    researcher.tier_service = MagicMock()
    researcher.settings_service = MagicMock()
    researcher.settings_service.get_setting.return_value = MagicMock(value="1")
    researcher.retriever = MagicMock()
    researcher.retriever.get_semantic_claims.return_value = []
    researcher.retriever.get_universe_knowledge_graph.return_value = {}
    researcher.uni_service.get_children.return_value = []
    researcher.workspace_service = MagicMock()
    researcher.exec_service = MagicMock()

    with patch("app.research.researcher.run_agent", side_effect=Exception("Boom")):
        with pytest.raises(Exception, match="Boom"):
            await researcher.research()

        researcher.exec_service.log_transition.assert_called_with(
            "test-run-id", "Research Unit", "Agent failed for TestUniverse: Boom", "FAILED", {}
        )
