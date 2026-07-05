import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.agents.nodes import log_transition, check_abort, audit_success, db_integrator_node
from app.core.runtime_state import ABORTED_RUNS

class TestLogTransition:
    def test_writes_execution_state(self, ephemeral_db):
        log_transition("test-run", "TestNode", "test thought", "IN_PROGRESS", {"key": "val"})
        from app.db.schema import ExecutionState
        from sqlmodel import select
        rows = ephemeral_db.exec(select(ExecutionState).where(ExecutionState.run_id == "test-run")).all()
        assert len(rows) >= 1
        assert rows[0].node_name == "TestNode"
        assert rows[0].thought == "test thought"
        assert rows[0].status == "IN_PROGRESS"

    def test_multi_log(self):
        log_transition("multi", "A", "t1", "IN_PROGRESS", {})
        log_transition("multi", "B", "t2", "COMPLETED", {})
        from app.db.schema import ExecutionState
        from sqlmodel import select, Session
        from app.db.session import engine
        with Session(engine) as session:
            rows = session.exec(select(ExecutionState).where(ExecutionState.run_id == "multi")).all()
            assert len(rows) == 2

    def test_empty_run_id(self):
        log_transition("", "EmptyRun", "thought", "OK", {})

    def test_special_chars_in_thought(self):
        log_transition("sp", "Node", "<script>alert(1)</script> & ' \"", "OK", {})

class TestCheckAbort:
    def setup_method(self):
        ABORTED_RUNS.clear()

    def test_no_abort(self):
        check_abort("safe-run")

    def test_aborted(self):
        ABORTED_RUNS.add("aborted-run")
        with pytest.raises(RuntimeError, match="aborted by user"):
            check_abort("aborted-run")

    def test_aborted_empty_string(self):
        ABORTED_RUNS.add("")
        with pytest.raises(RuntimeError):
            check_abort("")

class TestAuditSuccess:
    def test_success_keyword(self):
        assert audit_success("STATUS: SUCCESS") is True
        assert audit_success("SUCCESS") is True
        assert audit_success("  SUCCESS  ") is True

    def test_verified_keyword(self):
        assert audit_success("VERIFIED") is True
        assert audit_success("VERIFIED - All checks passed") is True

    def test_revision_required(self):
        assert audit_success("REVISION_REQUIRED") is False
        assert audit_success("REVISION REQUIRED") is False

    def test_mixed_case(self):
        assert audit_success("success") is True
        assert audit_success("revision_required") is False

    def test_empty_string(self):
        assert audit_success("") is False

    def test_random_text(self):
        assert audit_success("Something else entirely") is False

    def test_prefix_before_success(self):
        assert audit_success("Everything is SUCCESS") is True

    def test_revision_required_variants(self):
        assert audit_success("REVISION_REQUIRED: fix this") is False
        assert audit_success("REVISION REQUIRED: fix that") is False

class TestDBIntegratorNode:
    """Tests that the DB integrator runs integration then cleanup in a stateful session."""

    @pytest.mark.asyncio
    async def test_chained_session_execution(self):
        # Mock state
        state = {
            "run_id": "run-chain",
            "research_results": [
                {"name": "Universe-1", "summary": "Verified data for U1"}
            ]
        }
        
        # Mock run_agent to return different results for integration and cleanup
        integration_history = [{"role": "assistant", "content": "integrated"}]
        cleanup_history = [{"role": "assistant", "content": "cleaned"}]
        
        call_count = 0
        async def mock_run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "Integrated U1", integration_history
            return "Cleaned U1", cleanup_history

        with patch("app.agents.nodes.run_agent", side_effect=mock_run_agent), \
             patch("app.agents.nodes.set_current_universe"), \
             patch("app.agents.nodes.log_transition"), \
             patch("app.agents.nodes.Session"):
            
            result = await db_integrator_node(state)
            
            assert result["active_task"] == "SUMMARY"
            assert call_count == 2
