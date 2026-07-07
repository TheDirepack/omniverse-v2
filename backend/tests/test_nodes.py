from unittest.mock import patch
import uuid

import pytest
from app.agents.nodes import db_integrator_node
from app.core.runtime_state import ABORTED_RUNS, check_abort
from app.research.researcher import audit_success
from app.services.execution_service import ExecutionService


class TestLogTransition:
    @pytest.mark.asyncio
    async def test_writes_execution_state(self, session):
        exec_service = ExecutionService()
        exec_service.log_transition(
            "test-run", "TestNode", "test thought", "IN_PROGRESS", {"key": "val"}
        )
        from app.db.schema import ExecutionState
        from sqlmodel import select

        rows = session.exec(
            select(ExecutionState).where(ExecutionState.run_id == "test-run")
        ).all()
        assert len(rows) >= 1
        assert rows[0].node_name == "TestNode"
        assert rows[0].thought == "test thought"
        assert rows[0].status == "IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_multi_log(self):
        exec_service = ExecutionService()
        run_id = f"multi-{uuid.uuid4()}"
        exec_service.log_transition(run_id, "A", "t1", "IN_PROGRESS", {})
        exec_service.log_transition(run_id, "B", "t2", "COMPLETED", {})
        from app.db.schema import ExecutionState
        from app.db.session import engine
        from sqlmodel import Session, select

        with Session(engine) as session:
            rows = session.exec(
                select(ExecutionState).where(ExecutionState.run_id == run_id)
            ).all()
            assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_empty_run_id(self):
        exec_service = ExecutionService()
        exec_service.log_transition("", "EmptyRun", "thought", "OK", {})

    @pytest.mark.asyncio
    async def test_special_chars_in_thought(self):
        exec_service = ExecutionService()
        exec_service.log_transition(
            "sp", "Node", "<script>alert(1)</script> & ' \"", "OK", {}
        )


class TestCheckAbort:
    def setup_method(self):
        ABORTED_RUNS.clear()

    def test_no_abort(self):
        check_abort("safe-run")

    @pytest.mark.asyncio
    async def test_aborted(self):
        from app.core.runtime_state import abort_run
        await abort_run("aborted-run")
        with pytest.raises(RuntimeError, match="aborted by user"):
            check_abort("aborted-run")

    @pytest.mark.asyncio
    async def test_aborted_empty_string(self):
        from app.core.runtime_state import abort_run
        await abort_run("")
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
            ],
        }

        # Mock run_agent to return different results for integration and cleanup
        integration_history = [{"role": "assistant", "content": "integrated"}]
        cleanup_history = [{"role": "assistant", "content": "cleaned"}]

        call_count = 0

        async def mock_run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True, "Integrated U1", integration_history
            return True, "Cleaned U1", cleanup_history

        with (
            patch("app.agents.nodes.run_agent", side_effect=mock_run_agent),
            patch("app.agents.nodes.set_current_universe"),
            patch("app.services.execution_service.ExecutionService.log_transition"),
            patch("app.db.session.Session"),
        ):
            result = await db_integrator_node(state)

            assert result["active_task"] == "SUMMARY"
            assert call_count == 2
    @pytest.mark.asyncio
    async def test_integration_failure_detection(self):
        state = {
            "run_id": "run-fail",
            "research_results": [
                {"name": "Universe-1", "summary": "Verified data for U1"}
            ],
        }

        call_count = 0
        async def mock_run_agent(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate a failure that contains "Error"
                return False, "Error: Integration failed due to DB lock", []
            return True, "Cleaned U1", []

        with (
            patch("app.agents.nodes.run_agent", side_effect=mock_run_agent),
            patch("app.agents.nodes.set_current_universe"),
            patch("app.services.execution_service.ExecutionService.log_transition"),
            patch("app.db.session.Session"),
        ):
            # We don't care about the return value here as much as the call count
            try:
                await db_integrator_node(state)
            except Exception:
                pass
            
            # Should only have called run_agent ONCE (integration failed, so no cleanup)
            assert call_count == 1
