import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.knowledge_retriever import KnowledgeRetrieverService
from app.workflow.extrapolation_workflow import extrapolation_node
from app.workflow.tiering_workflow import architecture_node
from app.db.schema import Universe, TierSystem
from sqlmodel import Session
from app.db.session import engine

@pytest.mark.asyncio
async def test_get_claims_dataset_formatting():
    with Session(engine) as session:
        retriever = KnowledgeRetrieverService(session=session)
        with patch.object(retriever, 'get_universe_knowledge_graph') as mock_graph:
            mock_graph.return_value = {
                "Hero": {
                    "entity": "Hero",
                    "facts": [{"predicate": "has_power", "object": "Flight", "support": 5, "status": "VERIFIED", "reference": "ref1"}],
                    "related_entities": []
                }
            }
            dataset = retriever.get_claims_dataset(1)
            assert "(Hero --has_power--> Flight) [Support: 5]" in dataset

@pytest.mark.asyncio
async def test_extrapolation_revision_loop(monkeypatch):
    state = {
        "run_id": "extrap-rev",
        "verified_worlds": ["World1"],
    }
    
    mock_u = Universe(name="World1", id=1)
    
    # Mock UniverseService
    mock_uni_service = MagicMock()
    mock_uni_service.get_by_names.return_value = [mock_u]
    mock_repo = MagicMock()
    mock_repo.get_by_names.return_value = [mock_u]
    mock_uni_service.repo = mock_repo
    
    monkeypatch.setattr("app.workflow.extrapolation_workflow.UniverseService", lambda: mock_uni_service)
    
    mock_retriever = MagicMock()
    mock_retriever.get_claims_dataset.return_value = "Some claims"
    monkeypatch.setattr("app.workflow.extrapolation_workflow.KnowledgeRetrieverService", lambda: mock_retriever)

    mock_run = AsyncMock()
    mock_run.side_effect = [
        (True, "Theory 1", []),
        (True, "REVISION_REQUIRED: too vague", []),
        (True, "Theory 2 (refined)", []),
        (True, "VERIFIED: looks good", []),
    ]
    monkeypatch.setattr("app.workflow.extrapolation_workflow.run_agent", mock_run)
    monkeypatch.setattr("app.services.execution_service.ExecutionService.log_transition", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.theory_service.TheoryService.upsert_theory", lambda *args, **kwargs: None)

    result = await extrapolation_node(state)
    assert mock_run.call_count == 4
    assert result["generated_theories"][0]["theory"] == "Theory 2 (refined)"

@pytest.mark.asyncio
async def test_architecture_node_dataset_aggregation(monkeypatch):
    state = {
        "run_id": "arch-dataset",
        "verified_worlds": ["W1", "W2"],
        "anomalies": [],
        "architecture_attempts": 0
    }
    
    u1 = Universe(name="W1", id=1)
    u2 = Universe(name="W2", id=2)
    
    mock_repo = MagicMock()
    mock_repo.get_by_names.return_value = [u1, u2]
    
    mock_uni_service = MagicMock()
    mock_uni_service.repo = mock_repo
    mock_uni_service.get_by_names.return_value = [u1, u2]
    monkeypatch.setattr("app.workflow.tiering_workflow.UniverseService", lambda: mock_uni_service)
    
    mock_ret = MagicMock()
    dataset_values = ["Claims1", "Claims2"]
    def mock_get_dataset(uid):
        return dataset_values.pop(0) if dataset_values else "Default"
    mock_ret.get_claims_dataset.side_effect = mock_get_dataset
    monkeypatch.setattr("app.workflow.tiering_workflow.KnowledgeRetrieverService", lambda: mock_ret)

    monkeypatch.setattr("app.workflow.tiering_workflow.run_agent", AsyncMock(side_effect=[
        (True, "Rubric-V1", []), # Architect
        (True, "STATUS: STABLE\nTIER: 5\nJUSTIFICATION: la", []), # Stability check (1st world)
        (True, "STATUS: STABLE\nTIER: 6\nJUSTIFICATION: la", []), # Stability check (2nd world)
    ]))

    monkeypatch.setattr("app.workflow.tiering_workflow._audit_tier_system", AsyncMock(return_value=(True, "SUCCESS")))
    
    mock_tier_repo = MagicMock()
    mock_tier_repo.get_active_rubric.return_value = None
    
    from app.services.tiering_service import TieringService
    monkeypatch.setattr(TieringService, "repo", mock_tier_repo)
    
    monkeypatch.setattr("app.services.tiering_service.TieringService.create_rubric", lambda self, defn: TierSystem(name="Rubric", id=100, system_definition=defn))
    monkeypatch.setattr("app.services.execution_service.ExecutionService.log_transition", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.tiering_service.TieringService.slot_world", lambda self, *args, **kwargs: None)

    result = await architecture_node(state)
    assert result["system_stable"] is True
