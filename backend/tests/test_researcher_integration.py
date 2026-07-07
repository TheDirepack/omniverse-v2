import pytest
from unittest.mock import AsyncMock, patch
from app.research.researcher import research_single_world
from app.db.schema import Universe
from sqlmodel import Session
from app.db.session import engine

@pytest.mark.asyncio
async def test_research_single_world_integration_flow(mocker, clean_db):
    # Setup mock universe
    session = clean_db
    u = Universe(name="IntegrationWorld", slug="int-world")
    session.add(u)
    session.commit()
    u_uuid = u.uuid

    # Mock run_agent to simulate a successful research loop
    # First call: Researcher returns JSON
    # Second call: Auditor returns "SUCCESS"
    mock_run = AsyncMock()
    mock_run.side_effect = [
        (True, '{"Universe_Name": "IntegrationWorld", "Verified_Claims": [], "Knowledge_Graph": [], "Missing_Info": [], "Provisional_Conclusions": []}', []),
        (True, "STATUS: SUCCESS", []),
        (True, "STATUS: SUCCESS", []),
    ]
    
    mocker.patch("app.research.researcher.run_agent", mock_run)
    mock_retriever = mocker.patch("app.services.knowledge_retriever.KnowledgeRetrieverService", return_value=mocker.Mock())
    mock_retriever.return_value.get_semantic_claims.return_value = []
    mock_retriever.return_value.get_universe_knowledge_graph.return_value = {}
    mock_uni_service = mocker.patch("app.services.universe_service.UniverseService", return_value=mocker.Mock())
    mock_uni_service.return_value.get_universe_by_uuid.return_value = Universe(name="IntegrationWorld", id=1)
    mock_uni_service.return_value.get_children.return_value = []

    result = await research_single_world(u_uuid, "test-run")
    
    assert result["status"] == "VERIFIED"
    assert result["name"] == "IntegrationWorld"
    assert mock_run.call_count == 2

@pytest.mark.asyncio
async def test_research_single_world_min_turns_passed(mocker, clean_db):
    # Verify that run_agent is called with min_turns
    session = clean_db
    u = Universe(name="MinTurnsWorld", slug="min-turns")
    session.add(u)
    session.commit()
    u_uuid = u.uuid

    mock_run = AsyncMock()
    mock_run.return_value = (True, '{"Universe_Name": "MinTurnsWorld", "Verified_Claims": [], "Knowledge_Graph": [], "Missing_Info": [], "Provisional_Conclusions": []}', [])
    
    # We mock the auditor to succeed immediately
    mocker.patch("app.research.researcher.run_agent", mock_run)
    mock_uni_service = mocker.patch("app.services.universe_service.UniverseService", return_value=mocker.Mock())
    mock_uni_service.return_value.get_universe_by_uuid.return_value = Universe(name="MinTurnsWorld", id=1)
    mock_uni_service.return_value.get_children.return_value = []
    
    # Force audit to succeed to exit loop
    mock_run.side_effect = [
        (True, '{"Universe_Name": "MinTurnsWorld", "Verified_Claims": [], "Knowledge_Graph": [], "Missing_Info": [], "Provisional_Conclusions": []}', []),
        (True, "STATUS: SUCCESS", []),
        (True, "STATUS: SUCCESS", []),
    ]

    await research_single_world(u_uuid, "test-run")
    
    # Check first call to run_agent (Researcher) for min_turns
    args, kwargs = mock_run.call_args_list[0]
    assert "max_turns" in kwargs
    # The prompt uses min_turns internally in the loop logic but passed to run_agent as max_turns
    # Actually, in researcher.py: run_agent(..., max_turns=min_turns)
    assert kwargs["max_turns"] >= 6
