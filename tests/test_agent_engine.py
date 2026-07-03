"""
Tests for core/agent_engine.py — run_agent() loop.

All network/LLM calls are mocked via unittest.mock so these tests run offline.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.agent_engine import run_agent, FetchCache
from app.core.state import ABORTED_RUNS


def _make_response(content=None, tool_calls=None):
    """Build a minimal litellm-like response object."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_tool_call(name: str, args: dict, tc_id: str = "tc1"):
    tc = MagicMock()
    tc.id = tc_id
    tc.type = "function"
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


@pytest.fixture(autouse=True)
def clear_aborted():
    ABORTED_RUNS.clear()
    yield
    ABORTED_RUNS.clear()


class TestRunAgentDirectSubmit:
    """Agent calls the submit tool immediately on the first turn."""

    async def test_submit_on_first_turn(self):
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content="Here are my findings.", tool_calls=[submit_tc])

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=response)):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="You are a researcher.",
                user_prompt="Research Warhammer 40k.",
                step="research",
                run_id="run-001",
                tools_names=["webSearch"],
                submit_tool_name="submitFindings",
            )
        assert result == "Here are my findings."

    async def test_submit_returns_empty_content_as_default(self):
        """If content is None/empty when submit is called, return the fallback string."""
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content=None, tool_calls=[submit_tc])

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=response)):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-002",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert result == "Findings submitted."


class TestRunAgentToolLoop:
    """Agent uses a tool before submitting."""

    async def test_tool_result_injected_into_messages(self):
        web_tc = _make_tool_call("webSearch", {"search_query": "WH40k lore"}, tc_id="tc-search")
        submit_tc = _make_tool_call("submitFindings", {}, tc_id="tc-submit")

        search_response = _make_response(content="Searching...", tool_calls=[web_tc])
        submit_response = _make_response(content="Done researching.", tool_calls=[submit_tc])

        call_count = 0
        async def mock_run_model(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return search_response if call_count == 1 else submit_response

        captured_messages = []

        async def mock_web_search(args):
            captured_messages.append(args)
            return "Warhammer 40k is a sci-fi setting."

        with patch("app.core.agent_engine.router.run_model", new=mock_run_model), \
             patch("app.core.agent_engine.AGENT_TOOLS", {
                 "webSearch": {"func": mock_web_search, "description": "search", "parameters": {}},
             }):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-003",
                tools_names=["webSearch"],
                submit_tool_name="submitFindings",
            )

        assert result == "Done researching."
        assert captured_messages[0]["search_query"] == "WH40k lore"

    async def test_unknown_tool_call_returns_error_message(self):
        unknown_tc = _make_tool_call("unknownTool", {}, tc_id="tc-unk")
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0
        async def mock_run_model(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(content=None, tool_calls=[unknown_tc])
            return _make_response(content="submitted", tool_calls=[submit_tc])

        with patch("app.core.agent_engine.router.run_model", new=mock_run_model):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-004",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert result == "submitted"


class TestRunAgentMaxTurns:
    """When the agent never calls submit, max_turns should be reached."""

    async def test_max_turns_returns_error_string(self):
        # Always respond with plain text (no tool calls) — forces nudge path
        # then max_turns exceeded
        no_tool_response = _make_response(content=None, tool_calls=None)

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=no_tool_response)):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-max",
                tools_names=[],
                submit_tool_name="submitFindings",
                max_turns=2,
            )
        assert "Max turns reached" in result

    async def test_text_response_without_tool_calls_returns_content(self):
        """If the model returns plain text with no tool calls, return it immediately."""
        text_response = _make_response(content="Here is my answer.", tool_calls=None)

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=text_response)):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-text",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert result == "Here is my answer."


class TestRunAgentAbort:
    """Run aborts when run_id is in ABORTED_RUNS."""

    async def test_abort_raises_runtime_error(self):
        ABORTED_RUNS.add("run-aborted")

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock()) as mock_router:
            with pytest.raises(RuntimeError, match="aborted by user"):
                await run_agent(
                    agent_name="TEST",
                    system_prompt="sys",
                    user_prompt="user",
                    step="s",
                    run_id="run-aborted",
                    tools_names=[],
                    submit_tool_name="submitFindings",
                )
        # Router should never be called when already aborted
        mock_router.assert_not_called()


class TestRunAgentFetchCache:
    """Fetch cache is respected — already-cached URLs are not re-fetched."""

    async def test_cached_url_not_fetched_again(self):
        fetch_tc = _make_tool_call("fetchPage", {"urls": ["http://example.com"]}, tc_id="tc-fetch")
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0
        async def mock_router(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(content=None, tool_calls=[fetch_tc])
            return _make_response(content="done", tool_calls=[submit_tc])

        fetched_urls = []

        async def mock_fetch_page(url):
            fetched_urls.append(url)
            return "page content"

        cache = FetchCache()

        with patch("app.core.agent_engine.router.run_model", new=mock_router), \
             patch("app.core.agent_engine.AGENT_TOOLS", {}), \
             patch("app.core.web_fetch.web_fetcher.fetch_page", new=mock_fetch_page):
            # Pre-populate cache
            cache.set("http://example.com", "cached content")
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-cache",
                tools_names=["fetchPage"],
                submit_tool_name="submitFindings",
                fetch_cache=cache,
            )

        # The URL was already in the cache — web_fetcher.fetch_page should NOT be called
        assert "http://example.com" not in fetched_urls

    async def test_fetch_budget_limits_fetches(self):
        """When max_fetches is 1, only one URL is actually fetched; the second is skipped."""
        fetch_tc = _make_tool_call(
            "fetchPage",
            {"urls": ["http://a.com", "http://b.com"]},
            tc_id="tc-multi",
        )
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0
        async def mock_router(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_response(content=None, tool_calls=[fetch_tc])
            return _make_response(content="done", tool_calls=[submit_tc])

        fetched_urls = []

        async def mock_fetch_page(url):
            fetched_urls.append(url)
            return f"content of {url}"

        with patch("app.core.agent_engine.router.run_model", new=mock_router), \
             patch("app.core.agent_engine.AGENT_TOOLS", {}), \
             patch("app.core.web_fetch.web_fetcher.fetch_page", new=mock_fetch_page):
            await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-budget",
                tools_names=["fetchPage"],
                submit_tool_name="submitFindings",
                max_fetches=1,
            )

        assert len(fetched_urls) == 1
        assert fetched_urls[0] == "http://a.com"
