from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.browser import browser_manager
from app.core.web_search import WebSearcher
from bs4 import BeautifulSoup


@pytest.mark.asyncio
async def test_perform_search_unsupported_engine():
    searcher = WebSearcher()
    result = await searcher.perform_search("query", engine="unknown")
    assert result["status"] == "ERROR"
    assert "Unsupported engine: unknown" in result["message"]


@pytest.mark.asyncio
async def test_perform_search_site_filter():
    searcher = WebSearcher()
    with patch.object(
        browser_manager, "get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_get_page.return_value = (mock_page, mock_context)
        mock_page.content.return_value = "<html><body></body></html>"
        mock_page.goto = AsyncMock()

        await searcher.perform_search(
            "query", engine="google", site_filter="example.com"
        )

        # Verify query was modified with site filter
        args, _ = mock_page.goto.call_args
        url = args[0]
        assert "site%3Aexample.com%20query" in url


@pytest.mark.asyncio
async def test_parse_google():
    searcher = WebSearcher()
    html = """
    <div class="g">
        <a href="https://actual-link.com"><h3>Title 1</h3></a>
        <div class="VwiC3b">Snippet 1</div>
    </div>
    <div class="g">
        <h3>Title 2</h3>
        <a href="/url?q=https://link2.com&other=stuff">Link 2</a>
        <span class="st">Snippet 2</span>
    </div>
    <div class="g ai-container">
        <h3>AI Title</h3>
        <a href="https://ai.com"></a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    results = searcher._parse_google(soup)

    assert len(results) == 2
    assert results[0]["title"] == "Title 1"
    assert results[0]["url"] == "https://actual-link.com"
    assert "Snippet 1" in results[0]["snippet"]
    assert results[1]["title"] == "Title 2"
    assert results[1]["url"] == "https://link2.com"
    assert "Snippet 2" in results[1]["snippet"]


@pytest.mark.asyncio
async def test_parse_duckduckgo():
    searcher = WebSearcher()
    html = """
    <div class="result">
        <a class="result__a" href="https://ddg.com/1">Title 1</a>
        <div class="result__snippet">Snippet 1</div>
    </div>
    <div class="result">
        <a class="result__a" href="https://ddg.com/2">Title 2</a>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    results = searcher._parse_duckduckgo(soup)

    assert len(results) == 2
    assert results[0]["title"] == "Title 1"
    assert results[0]["url"] == "https://ddg.com/1"
    assert "Snippet 1" in results[0]["snippet"]
    assert results[1]["title"] == "Title 2"
    assert results[1]["url"] == "https://ddg.com/2"
    assert "" in results[1]["snippet"]


@pytest.mark.asyncio
async def test_parse_brave():
    searcher = WebSearcher()
    html = """
    <div class="snippet">
        <a class="snippet-title" href="https://brave.com/1">Title 1</a>
        <div class="snippet-description">Snippet 1</div>
    </div>
    <div class="snippet">
        <a data-label="title" href="https://brave.com/2">Title 2</a>
        <p class="snippet-description">Snippet 2</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    results = searcher._parse_brave(soup)

    assert len(results) == 2
    assert results[0]["title"] == "Title 1"
    assert results[0]["url"] == "https://brave.com/1"
    assert "Snippet 1" in results[0]["snippet"]
    assert results[1]["title"] == "Title 2"
    assert results[1]["url"] == "https://brave.com/2"
    assert "Snippet 2" in results[1]["snippet"]



def test_is_ai_container():
    searcher = WebSearcher()

    # Test positive matches (parent.select_one(selector) == element)
    soup_ai = BeautifulSoup("<div class='ai-result'></div>", "html.parser")
    element_ai = soup_ai.find("div")
    parent_ai = BeautifulSoup("<div></div>", "html.parser")
    parent_ai.append(element_ai)
    assert searcher._is_ai_container(element_ai) is True

    soup_featured = BeautifulSoup("<div id='featured-item'></div>", "html.parser")
    element_featured = soup_featured.find("div")
    parent_featured = BeautifulSoup("<div></div>", "html.parser")
    parent_featured.append(element_featured)
    assert searcher._is_ai_container(element_featured) is True

    # Test negative matches
    soup_normal = BeautifulSoup("<div>Normal</div>", "html.parser")
    element_normal = soup_normal.find("div")
    parent_normal = BeautifulSoup("<div></div>", "html.parser")
    parent_normal.append(element_normal)
    assert searcher._is_ai_container(element_normal) is False


@pytest.mark.asyncio
async def test_perform_search_detects_bot_check_page():
    searcher = WebSearcher()
    with patch.object(
        browser_manager, "get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_get_page.return_value = (mock_page, mock_context)
        mock_page.content.return_value = "<html><body>Our systems have detected unusual traffic from your network.</body></html>"
        mock_page.goto = AsyncMock()

        result = await searcher.perform_search("query", engine="google")

        assert result["status"] == "BLOCKED"
        assert "duckduckgo" in result["message"]
        assert "brave" in result["message"]


@pytest.mark.asyncio
async def test_perform_search_caps_results():
    searcher = WebSearcher()
    # 15 valid google-style results
    divs = "".join(
        f'<div class="g"><a href="https://site{i}.com"><h3>Title {i}</h3></a>'
        f'<div class="VwiC3b">Snippet {i}</div></div>'
        for i in range(15)
    )
    html = f"<html><body>{divs}</body></html>"

    with patch.object(
        browser_manager, "get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_get_page.return_value = (mock_page, mock_context)
        mock_page.content.return_value = html
        mock_page.goto = AsyncMock()

        result = await searcher.perform_search("query", engine="google")

        assert len(result["results"]) == 10


@pytest.mark.asyncio
async def test_perform_search_falls_back_on_navigation_timeout():
    searcher = WebSearcher()
    with patch.object(
        browser_manager, "get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_get_page.return_value = (mock_page, mock_context)
        mock_page.content.return_value = "<html><body></body></html>"
        # First call (networkidle) times out, second call (domcontentloaded) succeeds
        mock_page.goto = AsyncMock(
            side_effect=[Exception("Timeout 20000ms exceeded"), MagicMock()]
        )

        result = await searcher.perform_search("query", engine="google")

        assert mock_page.goto.call_count == 2
        assert result["status"] == "NO_RESULTS"
        assert "No results found" in result["message"]
