import pytest
from app.core.runtime_state import ABORTED_RUNS, ACTIVE_RUNS


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


class TestAsyncStateHelpers:
    @pytest.mark.asyncio
    async def test_add_active_run_async(self):
        from app.core.runtime_state import add_active_run, get_active_runs

        ACTIVE_RUNS.clear()
        await add_active_run("async-run-1")
        runs = await get_active_runs()
        assert "async-run-1" in runs

    @pytest.mark.asyncio
    async def test_abort_and_is_aborted_async(self):
        from app.core.runtime_state import abort_run, is_aborted

        ABORTED_RUNS.clear()
        assert not await is_aborted("abort-run-1")
        await abort_run("abort-run-1")
        assert await is_aborted("abort-run-1")

    @pytest.mark.asyncio
    async def test_remove_run_async(self):
        from app.core.runtime_state import (
            abort_run,
            add_active_run,
            get_active_runs,
            is_aborted,
            remove_run,
        )

        ACTIVE_RUNS.clear()
        ABORTED_RUNS.clear()

        await add_active_run("run-to-remove")
        await abort_run("run-to-remove")

        assert "run-to-remove" in await get_active_runs()
        assert await is_aborted("run-to-remove")

        await remove_run("run-to-remove")

        assert "run-to-remove" not in await get_active_runs()
        assert not await is_aborted("run-to-remove")
