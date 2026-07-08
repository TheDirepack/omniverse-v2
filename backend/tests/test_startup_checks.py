import pytest
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import ExecutionState, Setting, ProviderConfig, ProviderKey, AgentRouteFallback
from app.services.execution_service import ExecutionService
from app.services.settings_service import SettingsService

def test_reconcile_stale_runs(ephemeral_db):
    """Verify that interrupted runs are marked as FAILED on startup."""
    with Session(engine) as session:
        # Run 1: Already completed (should stay completed)
        session.add(ExecutionState(run_id="run-completed", node_name="End", thought="Done", status="COMPLETED", state_snapshot="{}"))
        
        # Run 2: Stale (last state is RESEARCHING)
        session.add(ExecutionState(run_id="run-stale", node_name="Researcher", thought="Searching...", status="RESEARCHING", state_snapshot="{}"))
        
        # Run 3: Stale (last state is INTEGRATING)
        session.add(ExecutionState(run_id="run-stale-2", node_name="Integrator", thought="Merging...", status="INTEGRATING", state_snapshot="{}"))
        
        # Run 4: Finished with error (should stay FAILED)
        session.add(ExecutionState(run_id="run-failed", node_name="Error", thought="Crashed", status="FAILED", state_snapshot="{}"))
        
        session.commit()

    exec_service = ExecutionService()
    exec_service.reconcile_stale_runs()

    with Session(engine) as session:
        # Check Run 1
        latest_1 = session.exec(select(ExecutionState).where(ExecutionState.run_id == "run-completed").order_by(ExecutionState.created_at.desc())).first()
        assert latest_1.status == "COMPLETED"

        # Check Run 2
        latest_2 = session.exec(select(ExecutionState).where(ExecutionState.run_id == "run-stale").order_by(ExecutionState.created_at.desc())).first()
        assert latest_2.status == "FAILED"
        assert "abandoned" in latest_2.thought

        # Check Run 3
        latest_3 = session.exec(select(ExecutionState).where(ExecutionState.run_id == "run-stale-2").order_by(ExecutionState.created_at.desc())).first()
        assert latest_3.status == "FAILED"

        # Check Run 4
        latest_4 = session.exec(select(ExecutionState).where(ExecutionState.run_id == "run-failed").order_by(ExecutionState.created_at.desc())).first()
        assert latest_4.status == "FAILED"

def test_validate_settings_errors(ephemeral_db):
    """Verify that configuration issues are detected by validate_settings."""
    from unittest.mock import patch
    
    settings_service = SettingsService()
    
    # Mock get_all_settings to return a configuration with various issues
    mock_data = {
        "general_settings": {
            # MIN_RESEARCH_TURNS is missing
        },
        "providers": [
            {
                "id": 1,
                "name": "EmptyProvider",
                "provider_type": "openai",
                "base_url": "http://test.com",
                "keys": [], # No keys
            },
            {
                "id": 2,
                "name": "EmptyKeyProvider",
                "provider_type": "openai",
                "base_url": "http://test.com",
                "keys": [{"id": 10, "api_key": "", "priority": 0}], # Empty key
            },
            {
                "id": 3,
                "name": "NoUrlProvider",
                "provider_type": "openai",
                "base_url": None, # Missing base_url
                "keys": [{"id": 11, "api_key": "sk-123", "priority": 0}],
            },
        ],
        "agent_routes": [
            {
                "id": 100,
                "task_type": "Researcher",
                "provider_id": 9999, # Non-existent provider
                "models": "gpt-4",
                "priority": 0,
            },
        ],
    }
    
    with patch.object(SettingsService, "get_all_settings", return_value=mock_data):
        issues = settings_service.validate_settings()
    
    issue_messages = [i["message"] for i in issues]
    
    assert any("MIN_RESEARCH_TURNS" in m and "missing" in m for m in issue_messages)
    assert any("EmptyProvider" in m and "no API keys" in m for m in issue_messages)
    assert any("EmptyKeyProvider" in m and "empty API key" in m for m in issue_messages)
    assert any("NoUrlProvider" in m and "missing base_url" in m for m in issue_messages)
    assert any("non-existent provider" in m and "9999" in m for m in issue_messages)

def test_validate_settings_valid(ephemeral_db):
    """Verify that a correct configuration returns no errors."""
    from app.db.settings_session import settings_engine
    
    with Session(settings_engine) as session:
        # Clear settings
        session.exec(select(Setting)).all() # Just to ensure we have a session
        # In a real test we'd clear the table, but ephemeral_db should handle it.
        # Let's just add valid ones.
        
        session.add(Setting(key="MIN_RESEARCH_TURNS", value="10"))
        
        p = ProviderConfig(name="ValidProvider", provider_type="openai", base_url="http://test.com")
        session.add(p)
        session.commit()
        session.refresh(p)
        session.add(ProviderKey(provider_id=p.id, api_key="sk-123"))
        
        session.add(AgentRouteFallback(task_type="Researcher", provider_id=p.id, models="gpt-4"))
        session.commit()

    settings_service = SettingsService()
    issues = settings_service.validate_settings()
    
    # Filter for ERRORs
    errors = [i for i in issues if i["severity"] == "ERROR"]
    assert len(errors) == 0
