import pytest
from app.core.tools import AGENT_TOOLS


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
        tool = AGENT_TOOLS["webSearch"]
        result = await tool["func"]({"search_query": ""})
        assert isinstance(result, str)

    @pytest.mark.slow
    async def test_special_chars(self):
        tool = AGENT_TOOLS["webSearch"]
        result = await tool["func"]({"search_query": "<script>alert(1)</script>"})
        assert isinstance(result, str)


class TestFetchPageTool:
    @pytest.mark.slow
    @pytest.mark.network
    async def test_invalid_url(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": ["not-a-valid-url"]})
        assert isinstance(result, str)

    async def test_missing_urls(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({})
        assert "Missing or invalid urls" in result

    @pytest.mark.slow
    async def test_urls_not_list(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": "http://example.com"})
        assert isinstance(result, str)

    async def test_empty_list(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": []})
        assert "Missing or invalid urls" in result

    async def test_none_in_list(self):
        tool = AGENT_TOOLS["fetchPage"]
        result = await tool["func"]({"urls": [None]})
        assert isinstance(result, str)


class TestRegistry:
    def test_has_web_search(self):
        assert "webSearch" in AGENT_TOOLS

    def test_has_fetch_page(self):
        assert "fetchPage" in AGENT_TOOLS

    def test_tool_function_is_callable(self):
        for name, info in AGENT_TOOLS.items():
            assert callable(info["func"]), f"{name}.func is not callable"
            assert isinstance(info["description"], str), f"{name}.description is not a string"
