from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.web_fetch import WebFetcher


def _mock_response(last_modified=None):
    response = MagicMock()
    response.headers = {"last-modified": last_modified} if last_modified else {}
    return response


def _patch_bm():
    """Set up common browser_manager mock with a page that can survive
    _dismiss_cookie_banners (Playwright locator chain)."""
    locator = MagicMock()
    locator.is_visible = AsyncMock(return_value=False)

    mock_page = MagicMock()
    mock_page.goto = AsyncMock(return_value=_mock_response())
    mock_page.content = AsyncMock(return_value="<html><body><p>Hello World</p></body></html>")
    mock_page.url = "https://example.com"
    mock_page.get_by_role = MagicMock(return_value=MagicMock(first=locator))
    mock_page.close = AsyncMock()
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.press = AsyncMock()

    mock_context = AsyncMock()
    mock_context.close = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_bm = MagicMock()
    mock_bm.get_page = AsyncMock(return_value=(mock_page, mock_context))
    mock_bm.release_page = AsyncMock()
    return patch("app.core.web_fetch.browser_manager", mock_bm), mock_bm


@pytest.mark.asyncio
async def test_fetch_page_success_no_freshness():
    """With include_freshness=False, behavior matches the old plain-text extraction."""
    patcher, mock_bm = _patch_bm()
    with patcher:
        fetcher = WebFetcher()
        result = await fetcher.fetch_page(
            "https://example.com", include_freshness=False
        )

        assert result["main_content"] == "Hello World"


@pytest.mark.asyncio
async def test_fetch_page_includes_freshness_signals_by_default():
    patcher, mock_bm = _patch_bm()
    with patcher:
        mock_page = mock_bm.get_page.return_value[0]
        mock_page.goto = AsyncMock(
            return_value=_mock_response(last_modified="Wed, 01 Jan 2025 00:00:00 GMT")
        )

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert "[SOURCE FRESHNESS SIGNALS]" in result["freshness"]
        assert "Hello World" in result["main_content"]
        assert "Wed, 01 Jan 2025 00:00:00 GMT" in result["freshness"]
        assert "Redirect occurred: NO" in result["freshness"]


@pytest.mark.asyncio
async def test_fetch_page_detects_redirect_and_staleness():
    patcher, mock_bm = _patch_bm()
    with patcher:
        mock_page = mock_bm.get_page.return_value[0]
        mock_page.content = AsyncMock(
            return_value="<html><body><p>This wiki has moved to newsite.example</p></body></html>"
        )
        mock_page.url = "https://old.example.com/redirected"

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert "Redirect occurred: YES" in result["freshness"]
        assert "STALENESS WARNING" in result["freshness"]


@pytest.mark.asyncio
async def test_fetch_page_falls_back_on_networkidle_timeout():
    patcher, mock_bm = _patch_bm()
    with patcher:
        mock_page = mock_bm.get_page.return_value[0]
        mock_page.goto = AsyncMock(
            side_effect=[TimeoutError("Timeout 20000ms exceeded"), _mock_response()]
        )

        fetcher = WebFetcher()
        result = await fetcher.fetch_page(
            "https://example.com", include_freshness=False
        )

        assert result["main_content"] == "Hello World"
        assert mock_page.goto.call_count == 2
        mock_page.goto.assert_any_call(
            "https://example.com", wait_until="networkidle", timeout=20000
        )
        mock_page.goto.assert_any_call(
            "https://example.com", wait_until="domcontentloaded", timeout=15000
        )


@pytest.mark.asyncio
async def test_fetch_page_invalid_protocol():
    fetcher = WebFetcher()
    with pytest.raises(ValueError, match="Invalid protocol"):
        await fetcher.fetch_page("ftp://example.com")


@pytest.mark.asyncio
async def test_fetch_page_missing_hostname():
    fetcher = WebFetcher()
    with pytest.raises(ValueError, match="Hostname missing"):
        await fetcher.fetch_page("https://")


@pytest.mark.asyncio
async def test_fetch_page_internal_hostname():
    fetcher = WebFetcher()
    with pytest.raises(ValueError, match="Internal resource forbidden"):
        await fetcher.fetch_page("http://localhost")

    with pytest.raises(ValueError, match="Internal resource forbidden"):
        await fetcher.fetch_page("http://example.local")


@pytest.mark.asyncio
async def test_fetch_page_private_ip():
    fetcher = WebFetcher()
    with patch("socket.gethostbyname", return_value="192.168.1.1"), pytest.raises(
        ValueError, match="Private IP forbidden"
    ):
        await fetcher.fetch_page("http://192.168.1.1")

    with patch("socket.gethostbyname", return_value="169.254.169.254"), pytest.raises(
        ValueError, match="Internal resource forbidden"
    ):
        await fetcher.fetch_page("http://169.254.169.254")


@pytest.mark.asyncio
async def test_fetch_page_truncation():
    patcher, mock_bm = _patch_bm()
    with patcher:
        mock_page = mock_bm.get_page.return_value[0]
        long_text = "a" * 25000
        mock_page.content = AsyncMock(return_value=f"<html><body>{long_text}</body></html>")

        fetcher = WebFetcher()
        result = await fetcher.fetch_page("https://example.com")

        assert len(result["main_content"]) > 20000
        assert len(result["main_content"]) <= 30000
