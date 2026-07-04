import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.browser import BrowserManager

@pytest.mark.asyncio
async def test_browser_manager_start_stop():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        mock_browser = AsyncMock()
        mock_launch.return_value = mock_browser
        
        await manager.start()
        assert manager.browser == mock_browser
        mock_launch.assert_called_once()
        
        await manager.stop()
        assert manager.browser is None
        mock_browser.close.assert_called_once()

@pytest.mark.asyncio
async def test_get_page_not_started():
    manager = BrowserManager()
    with pytest.raises(RuntimeError, match="BrowserManager not started"):
        await manager.get_page()

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
        assert manager.semaphore._value == 4  # 5 - 1

        manager.release_page(context)
        assert manager.semaphore._value == 5

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
        
        assert manager.semaphore._value == 5

@pytest.mark.asyncio
async def test_semaphore_limiting():
    with patch("app.core.browser.launch_async", new=AsyncMock()) as mock_launch:
        manager = BrowserManager()
        mock_browser = AsyncMock()
        mock_launch.return_value = mock_browser
        
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        await manager.start()

        # Acquire 5 slots
        pages_and_contexts = []
        for _ in range(5):
            pages_and_contexts.append(await manager.get_page())
        
        assert manager.semaphore._value == 0

        # Attempt to acquire 6th slot - should block. We'll use a timeout to fail.
        try:
            await asyncio.wait_for(manager.get_page(), timeout=0.1)
            pytest.fail("Should have timed out")
        except asyncio.TimeoutError:
            pass

        # Release one and check if we can acquire
        page, context = pages_and_contexts[0]
        manager.release_page(context)
        assert manager.semaphore._value == 1
        
        # Now we should be able to get a page
        page2, context2 = await asyncio.wait_for(manager.get_page(), timeout=0.5)
        assert page2 == mock_page
        assert context2 == mock_context
        assert manager.semaphore._value == 0
