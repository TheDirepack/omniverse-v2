import pytest
from app.core.state import ACTIVE_RUNS, ABORTED_RUNS


class TestActiveRuns:
    def setup_method(self):
        ACTIVE_RUNS.clear()
        ABORTED_RUNS.clear()

    def test_add(self):
        ACTIVE_RUNS.add("run-1")
        assert "run-1" in ACTIVE_RUNS

    def test_remove(self):
        ACTIVE_RUNS.add("run-1")
        ACTIVE_RUNS.discard("run-1")
        assert "run-1" not in ACTIVE_RUNS

    def test_discard_nonexistent(self):
        ACTIVE_RUNS.discard("does-not-exist")

    def test_multiple_isolation(self):
        ACTIVE_RUNS.add("a")
        ACTIVE_RUNS.add("b")
        assert "a" in ACTIVE_RUNS
        assert "b" in ACTIVE_RUNS
        ACTIVE_RUNS.discard("a")
        assert "a" not in ACTIVE_RUNS
        assert "b" in ACTIVE_RUNS

    def test_empty_string(self):
        ACTIVE_RUNS.add("")
        assert "" in ACTIVE_RUNS


class TestAbortedRuns:
    def setup_method(self):
        ACTIVE_RUNS.clear()
        ABORTED_RUNS.clear()

    def test_add_check(self):
        ABORTED_RUNS.add("run-1")
        assert "run-1" in ABORTED_RUNS

    def test_membership(self):
        assert "nonexistent" not in ABORTED_RUNS

    def test_empty_string(self):
        ABORTED_RUNS.add("")
        assert "" in ABORTED_RUNS

    def test_isolation_from_active(self):
        ACTIVE_RUNS.add("shared")
        assert "shared" not in ABORTED_RUNS
