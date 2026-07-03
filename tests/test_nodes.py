import pytest
from app.agents.nodes import log_transition, check_abort, audit_success
from app.core.state import ABORTED_RUNS


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
