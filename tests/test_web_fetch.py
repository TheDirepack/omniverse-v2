import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.web_fetch import WebFetcher

def _mock_response(last_modified=None):
    response = MagicMock()
    response.headers = {"last-modified": last_modified} if last_modified else {}
    return response


@pytest.mark.asyncio
async def test_fetch_page_success_no_freshness():
    """With include_freshness=False, behavior matches the old plain-text extraction."""
    with patch("app.core.web_fetch.browser_manager") as mock_bm:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_bm.get_page = AsyncMock(return_value=(mock_page, mock_context))

        mock_page.content.return_value = "<html><body><p>Hello World</p></body></html>"
        mock_page.goto = AsyncMock(return_value=_mock_response())
        mock_page.url = "https://example.com"

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com", include_freshness=False)

        assert result == "Hello World"
        mock_page.goto.assert_called_once_with("https://example.com", wait_until="networkidle")
        mock_page.close.assert_called_once()
        mock_context.close.assert_called_once()
        mock_bm.release_page.assert_called_once_with(mock_context)


@pytest.mark.asyncio
async def test_fetch_page_includes_freshness_signals_by_default():
    with patch("app.core.web_fetch.browser_manager") as mock_bm:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_bm.get_page = AsyncMock(return_value=(mock_page, mock_context))

        mock_page.content.return_value = "<html><body><p>Hello World</p></body></html>"
        mock_page.goto = AsyncMock(return_value=_mock_response(last_modified="Wed, 01 Jan 2025 00:00:00 GMT"))
        mock_page.url = "https://example.com"

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert "[SOURCE FRESHNESS SIGNALS]" in result
        assert "Hello World" in result
        assert "Wed, 01 Jan 2025 00:00:00 GMT" in result
        assert "Redirect occurred: NO" in result


@pytest.mark.asyncio
async def test_fetch_page_detects_redirect_and_staleness():
    with patch("app.core.web_fetch.browser_manager") as mock_bm:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_bm.get_page = AsyncMock(return_value=(mock_page, mock_context))

        mock_page.content.return_value = "<html><body><p>This wiki has moved to newsite.example</p></body></html>"
        mock_page.goto = AsyncMock(return_value=_mock_response())
        mock_page.url = "https://old.example.com/redirected"

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert "Redirect occurred: YES" in result
        assert "STALENESS WARNING" in result

@pytest.mark.asyncio
async def test_fetch_page_invalid_protocol():
    fetcher = WebFetcher()
    with pytest.raises(ValueError, match="Invalid protocol"):
        await fetcher.fetch_page("ftp://example.com")

@pytest.mark.asyncio
async def test_fetch_page_missing_hostname():
    fetcher = WebFetcher()
    with pytest.raises(ValueError, match="hostname missing"):
        await fetcher.fetch_page("https://")

@pytest.mark.asyncio
async def test_fetch_page_internal_hostname():
    fetcher = WebFetcher()
    with pytest.raises(ValueError, match="Access to internal resource localhost is forbidden"):
        await fetcher.fetch_page("http://localhost")
    
    with pytest.raises(ValueError, match="Access to internal resource example.local is forbidden"):
        await fetcher.fetch_page("http://example.local")

@pytest.mark.asyncio
async def test_fetch_page_private_ip():
    fetcher = WebFetcher()
    with patch("socket.gethostbyname", return_value="192.168.1.1"):
        with pytest.raises(ValueError, match="Access to private IP 192.168.1.1 is forbidden"):
            await fetcher.fetch_page("http://192.168.1.1")

    with patch("socket.gethostbyname", return_value="169.254.169.254"):
        with pytest.raises(ValueError, match="Access to internal resource 169.254.169.254 is forbidden"):
            await fetcher.fetch_page("http://169.254.169.254")

@pytest.mark.asyncio
async def test_fetch_page_truncation():
    with patch("app.core.web_fetch.browser_manager") as mock_bm:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_bm.get_page = AsyncMock(return_value=(mock_page, mock_context))
        
        long_text = "a" * 25000
        mock_page.content.return_value = f"<html><body>{long_text}</body></html>"
        mock_page.goto = AsyncMock()

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert len(result) > 20000
        assert "... [truncated at 20,000 characters]" in result
