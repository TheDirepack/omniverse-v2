import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bs4 import BeautifulSoup
from app.core.web_search import WebSearcher
from app.core.browser import browser_manager

@pytest.mark.asyncio
async def test_perform_search_unsupported_engine():
    searcher = WebSearcher()
    result = await searcher.perform_search("query", engine="unknown")
    assert "Unsupported engine: unknown" in result

@pytest.mark.asyncio
async def test_perform_search_site_filter():
    searcher = WebSearcher()
    with patch.object(browser_manager, "get_page", new_callable=AsyncMock) as mock_get_page:
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_get_page.return_value = (mock_page, mock_context)
        mock_page.content.return_value = "<html><body></body></html>"
        mock_page.goto = AsyncMock()

        await searcher.perform_search("query", engine="google", site_filter="example.com")
        
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
    assert "### 1. [Title 1](https://actual-link.com)" in results[0]
    assert "Snippet 1" in results[0]
    assert "### 2. [Title 2](https://link2.com)" in results[1]
    assert "Snippet 2" in results[1]

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
    assert "### 1. [Title 1](https://ddg.com/1)" in results[0]
    assert "Snippet 1" in results[0]
    assert "### 2. [Title 2](https://ddg.com/2)" in results[1]
    assert "" in results[1]

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
    assert "### 1. [Title 1](https://brave.com/1)" in results[0]
    assert "Snippet 1" in results[0]
    assert "### 2. [Title 2](https://brave.com/2)" in results[1]
    assert "Snippet 2" in results[1]

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
