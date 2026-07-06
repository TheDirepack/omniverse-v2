"""
Tests for the agent tool registry (webSearch, fetchPage) and AGENT_TOOLS structure.

Note: asyncio_mode = auto is set in pytest.ini so all async test functions
are automatically treated as coroutines without needing @pytest.mark.asyncio.
"""
import pytest
from app.core.tools import AGENT_TOOLS
from app.core.browser import browser_manager


@pytest.fixture(autouse=True, scope="module")
async def setup_browser():
    await browser_manager.start()
    yield
    await browser_manager.stop()


class TestWebSearchTool:
    @pytest.mark.slow
    @pytest.mark.network
    async def test_success(self):
        tool = AGENT_TOOLS["webSearch"]
        result = await tool["func"]({"search_query": "Warhammer 40k"})
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_missing_query(self):
        tool = AGENT_TOOLS["webSearch"]
        result = await tool["func"]({})
        assert result == "Error: Missing search_query argument."

    async def test_empty_query(self):
        """Empty string query should not raise — returns a string (possibly empty or error)."""
        tool = AGENT_TOOLS["webSearch"]
        result = await tool["func"]({"search_query": ""})
        # Missing query guard triggers on falsy empty string
        assert result == "Error: Missing search_query argument."

    @pytest.mark.slow
    @pytest.mark.network
    async def test_special_chars(self):
        tool = AGENT_TOOLS["webSearch"]
        result = await tool["func"]({"search_query": "<script>alert(1)</script>"})
        assert isinstance(result, str)


class TestFetchPageTool:
    @pytest.mark.slow
    @pytest.mark.network
    async def test_invalid_url(self):
        """An invalid URL should return an error string, not raise."""
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": ["not-a-valid-url"]})
        assert isinstance(result, str)

    async def test_missing_urls(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({})
        assert "Missing or invalid urls" in result

    @pytest.mark.slow
    @pytest.mark.network
    async def test_urls_not_list_but_string(self):
        """A bare string in 'urls' (not a list) is coerced to a single-item list."""
        tool = AGENT_TOOLS["fetchPage"]
        # The tool handles string by wrapping into [str]; slow/network to actually fetch
        result = await tool["func"]({"urls": "http://example.com"})
        # On environments without a browser, this may return an error string
        assert isinstance(result, str)

    async def test_empty_list(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": []})
        assert "Missing or invalid urls" in result

    async def test_none_in_list(self):
        """A None element in the urls list should not crash the tool."""
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": [None]})
        # Tool iterates the list; None url may error gracefully or produce output
        assert isinstance(result, str)


class TestRegistry:
    def test_has_web_search(self):
        assert "webSearch" in AGENT_TOOLS

    def test_has_fetch_page(self):
        assert "fetchPage" in AGENT_TOOLS

    def test_has_all_db_tools(self):
        for name in ["queryTraits", "upsertTrait", "queryUnconfirmedTraits",
                     "saveUnconfirmedTrait", "deleteUnconfirmedTrait"]:
            assert name in AGENT_TOOLS, f"Missing tool: {name}"

    def test_tool_function_is_callable(self):
        for name, info in AGENT_TOOLS.items():
            assert callable(info["func"]), f"{name}.func is not callable"
            assert isinstance(info["description"], str), f"{name}.description is not a string"

    def test_tool_has_parameters_schema(self):
        for name, info in AGENT_TOOLS.items():
            assert "parameters" in info, f"{name} missing parameters schema"
            assert info["parameters"].get("type") == "object", \
                f"{name}.parameters.type must be 'object'"
