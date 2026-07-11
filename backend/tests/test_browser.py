import asyncio
import importlib
import os
from unittest.mock import AsyncMock, patch

import pytest

from app.core.browser import BROWSER_MAX_CONCURRENCY_PER_INSTANCE, BrowserManager


@pytest.mark.asyncio
async def test_browser_manager_start_stop():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        mock_browser = AsyncMock()
        mock_launch.return_value = mock_browser

        await manager.start()
        # start() is a no-op; browsers launch lazily on first get_page()
        assert all(slot.browser is None for slot in manager.pool)
        mock_launch.assert_not_called()

        await manager.get_page()
        assert manager.browser == mock_browser
        mock_launch.assert_called_once()

        await manager.stop()
        assert all(slot.browser is None for slot in manager.pool)
        mock_browser.close.assert_called_once()

@pytest.mark.asyncio
async def test_get_page_lazy_loading():
    manager = BrowserManager()
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        await manager.get_page()
        mock_launch.assert_called_once()

@pytest.mark.asyncio
async def test_get_page_success():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        mock_browser = AsyncMock()
        mock_launch.return_value = mock_browser

        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        await manager.start()
        page, context = await manager.get_page()

        assert page == mock_page
        assert context == mock_context
        slot = manager.pool[0]
        assert slot.active_contexts == 1
        assert slot.semaphore._value == BROWSER_MAX_CONCURRENCY_PER_INSTANCE - 1

        manager.release_page(context)
        assert slot.active_contexts == 0
        assert slot.semaphore._value == BROWSER_MAX_CONCURRENCY_PER_INSTANCE

@pytest.mark.asyncio
async def test_get_page_error_releases_semaphore():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        mock_browser = AsyncMock()
        mock_launch.return_value = mock_browser

        mock_browser.new_context.side_effect = Exception("Failed to create context")

        await manager.start()
        with pytest.raises(Exception, match="Failed to create context"):
            await manager.get_page()

        slot = manager.pool[0]
        assert slot.semaphore._value == BROWSER_MAX_CONCURRENCY_PER_INSTANCE
        assert slot.active_contexts == 0

@pytest.mark.asyncio
async def test_semaphore_limiting_per_slot():
    """With pool size forced to 1, concurrency is still capped per-instance."""
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        manager.pool = manager.pool[:1]  # force single slot for this test
        mock_browser = AsyncMock()
        mock_launch.return_value = mock_browser

        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        await manager.start()

        limit = BROWSER_MAX_CONCURRENCY_PER_INSTANCE
        pages_and_contexts = [await manager.get_page() for _ in range(limit)]

        assert manager.pool[0].semaphore._value == 0

        try:
            await asyncio.wait_for(manager.get_page(), timeout=0.1)
            pytest.fail("Should have timed out")
        except asyncio.TimeoutError:
            pass

        _page, context = pages_and_contexts[0]
        manager.release_page(context)
        assert manager.pool[0].semaphore._value == 1

        page2, context2 = await asyncio.wait_for(manager.get_page(), timeout=0.5)
        assert page2 == mock_page
        assert context2 == mock_context

@pytest.mark.asyncio
async def test_pool_spreads_load_across_slots():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        assert len(manager.pool) >= 2, "pool should have multiple slots by default"

        mock_browsers = [AsyncMock() for _ in manager.pool]
        mock_launch.side_effect = mock_browsers

        for browser in mock_browsers:
            ctx = AsyncMock()
            page = AsyncMock()
            browser.new_context.return_value = ctx
            ctx.new_page.return_value = page

        # First get_page should land on slot 0 (least loaded, tie -> first)
        _p1, c1 = await manager.get_page()
        assert manager.pool[0].active_contexts == 1

        # Second get_page should land on the next least-loaded slot (slot 1)
        _p2, c2 = await manager.get_page()
        assert manager.pool[1].active_contexts == 1

        manager.release_page(c1)
        manager.release_page(c2)
        assert all(s.active_contexts == 0 for s in manager.pool)

@pytest.mark.asyncio
async def test_relaunch_on_dead_browser():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        manager.pool = manager.pool[:1]

        dead_browser = AsyncMock()
        dead_browser.new_context.side_effect = Exception("crashed")

        fresh_browser = AsyncMock()
        fresh_ctx = AsyncMock()
        fresh_page = AsyncMock()
        fresh_browser.new_context.return_value = fresh_ctx
        fresh_ctx.new_page.return_value = fresh_page

        # First call to launch_async gives dead, second gives fresh
        mock_launch.side_effect = [dead_browser, fresh_browser]

        # This call should trigger the internal retry:
        # 1. ensure_launched -> dead_browser
        # 2. new_context -> crash
        # 3. relaunch -> fresh_browser
        # 4. new_context -> success
        page, context = await manager.get_page()

        assert page == fresh_page
        assert context == fresh_ctx
        assert mock_launch.call_count == 2

@pytest.mark.asyncio
async def test_pool_status_reports_slots():
    manager = BrowserManager()
    status = manager.pool_status()
    assert len(status) == len(manager.pool)
    for entry in status:
        assert "slot" in entry
        assert "launched" in entry
        assert "active_contexts" in entry

@pytest.mark.asyncio
async def test_browser_config_env_vars():
    """Verify that BROWSER_POOL_SIZE and BROWSER_MAX_CONCURRENCY_PER_INSTANCE
    are respected."""
    custom_pool_size = "4"
    custom_concurrency = "10"

    with patch.dict(os.environ, {
        "BROWSER_POOL_SIZE": custom_pool_size,
        "BROWSER_MAX_CONCURRENCY_PER_INSTANCE": custom_concurrency
    }):
        # Reload the module to pick up new env vars
        import app.core.browser
        importlib.reload(app.core.browser)

        manager = app.core.browser.BrowserManager()
        assert len(manager.pool) == int(custom_pool_size)
        assert manager.pool[0].semaphore._value == int(custom_concurrency)

@pytest.mark.asyncio
async def test_browser_update_config():
    """Verify that update_config dynamically rebuilds the pool."""
    manager = BrowserManager()
    initial_size = len(manager.pool)

    await manager.update_config(pool_size=5, max_concurrency=12)

    assert len(manager.pool) == 5
    assert manager.pool[0].semaphore._value == 12
    assert initial_size != 5
