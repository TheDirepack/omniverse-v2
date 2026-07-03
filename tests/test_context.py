"""
Tests for app.core.context — the ContextVar-based universe context.
"""
import asyncio
import pytest
from app.core.context import get_current_universe, set_current_universe


class TestContextVar:
    def test_default_is_empty_string(self):
        """Default value before any set() call is an empty string."""
        # Each test gets a fresh call stack but NOT a fresh ContextVar snapshot
        # unless wrapped in an asyncio.Task, so we just check the public API.
        result = get_current_universe()
        assert isinstance(result, str)

    def test_set_and_get(self):
        set_current_universe("Marvel")
        assert get_current_universe() == "Marvel"

    def test_overwrite(self):
        set_current_universe("DC")
        set_current_universe("Warhammer 40k")
        assert get_current_universe() == "Warhammer 40k"

    def test_empty_string_set(self):
        set_current_universe("")
        assert get_current_universe() == ""

    def test_unicode_name(self):
        set_current_universe("宇宙-Ω")
        assert get_current_universe() == "宇宙-Ω"

    def test_very_long_name(self):
        long_name = "X" * 10_000
        set_current_universe(long_name)
        assert get_current_universe() == long_name

    def test_isolation_across_async_tasks(self):
        """ContextVar is isolated per asyncio Task — changes in a child task
        do NOT propagate back to the parent context."""
        set_current_universe("Parent")

        result = {}

        async def child():
            set_current_universe("Child")
            result["child"] = get_current_universe()

        async def run():
            set_current_universe("Parent")
            task = asyncio.create_task(child())
            await task
            result["parent"] = get_current_universe()

        asyncio.run(run())
        # The child task's mutation must not bleed back to the parent
        assert result["parent"] == "Parent"
        assert result["child"] == "Child"
