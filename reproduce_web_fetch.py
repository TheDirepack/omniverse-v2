import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.web_fetch import WebFetcher

@pytest.mark.asyncio
async def test_fetch_page_success():
    with patch("app.core.web_fetch.browser_manager") as mock_bm:
        print(f"\nType of get_page: {type(mock_bm.get_page)}")
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_bm.get_page.return_value = (mock_page, mock_context)
        
        mock_page.content.return_value = "<html><body><p>Hello World</p></body></html>"
        mock_page.goto = AsyncMock()

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert result == "Hello World"
        mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle")
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
        mock_bm.release_page.assert_called_once_with(mock_context)
