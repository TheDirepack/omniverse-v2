"""
Tests for core/agent_engine.py — run_agent() loop.

All network/LLM calls are mocked via unittest.mock so these tests run offline.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.agent_engine import run_agent, FetchCache
from app.core.runtime_state import ABORTED_RUNS
from app.core.tools import AGENT_TOOLS


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

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=(response, "mock-model", "mock-key"))):
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

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=(response, "mock-model", "mock-key"))):
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
            return (search_response, "model", "key") if call_count == 1 else (submit_response, "model", "key")

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
                return (_make_response(content=None, tool_calls=[unknown_tc]), "m", "k")
            return (_make_response(content="submitted", tool_calls=[submit_tc]), "m", "k")

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

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=(no_tool_response, "m", "k"))):
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
        assert "MAX_TURNS_REACHED" in result

    async def test_text_response_without_tool_calls_returns_content(self):
        """If the model returns plain text with no tool calls, return it immediately."""
        text_response = _make_response(content="Here is my answer.", tool_calls=None)

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=(text_response, "m", "k"))):
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
                return (_make_response(content=None, tool_calls=[fetch_tc]), "m", "k")
            return (_make_response(content="done", tool_calls=[submit_tc]), "m", "k")

        fetched_urls = []


        async def mock_fetch_page(url):
            fetched_urls.append(url)
            return "page content"

        cache = FetchCache()

        with patch("app.core.agent_engine.router.run_model", new=mock_router), \
             patch("app.core.agent_engine.AGENT_TOOLS", {
                 "fetchPage": {"func": AsyncMock(), "description": "fetch", "parameters": {}}
             }), \
             patch("app.core.web_fetch.web_fetcher.fetch_page", new=mock_fetch_page):
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
                return (_make_response(content=None, tool_calls=[fetch_tc]), "m", "k")
            return (_make_response(content="done", tool_calls=[submit_tc]), "m", "k")

        fetched_urls = []


        async def mock_fetch_page(url):
            fetched_urls.append(url)
            return f"content of {url}"

        with patch("app.core.agent_engine.router.run_model", new=mock_router), \
             patch("app.core.agent_engine.AGENT_TOOLS", {
                 "fetchPage": {"func": AsyncMock(), "description": "fetch", "parameters": {}}
             }), \
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

    async def test_compare_source_freshness_shares_budget_with_fetch_page(self):
        """
        Regression test: compareSourceFreshness must draw from the SAME
        per-run fetch budget as fetchPage, not perform its own unbudgeted
        fetches. Here fetchPage already uses up the only fetch slot, so
        compareSourceFreshness's candidate URL should be reported as
        budget-exhausted rather than actually fetched.
        """
        fetch_tc = _make_tool_call("fetchPage", {"urls": ["http://a.com"]}, tc_id="tc-fetch")
        compare_tc = _make_tool_call(
            "compareSourceFreshness", {"urls": ["http://b.com", "http://c.com"]}, tc_id="tc-compare"
        )
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0
        async def mock_router(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[fetch_tc]), "m", "k")
            if call_count == 2:
                return (_make_response(content=None, tool_calls=[compare_tc]), "m", "k")
            return (_make_response(content="done", tool_calls=[submit_tc]), "m", "k")

        fetched_urls = []

        async def mock_fetch_page(url):
            fetched_urls.append(url)
            return f"content of {url}"

        with patch("app.core.agent_engine.router.run_model", new=mock_router), \
             patch("app.core.agent_engine.AGENT_TOOLS", AGENT_TOOLS), \
             patch("app.core.web_fetch.web_fetcher.fetch_page", new=mock_fetch_page):
            result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-shared-budget",
                tools_names=["fetchPage", "compareSourceFreshness"],
                submit_tool_name="submitFindings",
                max_fetches=1,
            )

        # Only the fetchPage call should have consumed the single fetch slot;
        # neither candidate in compareSourceFreshness should have been fetched.
        assert fetched_urls == ["http://a.com"]


class TestReadPageWithBudget:
    """Direct tests of the shared cache/budget helper, independent of the
    (currently broken in this environment) router-mocking harness used above."""

    async def test_cache_hit_does_not_fetch_and_does_not_consume_budget(self):
        from app.core.agent_engine import _read_page_with_budget
        cache = FetchCache()
        cache.set("http://cached.com", "cached content")

        with patch("app.core.web_fetch.web_fetcher.fetch_page", new=AsyncMock(side_effect=AssertionError("should not fetch"))):
            content, new_count, status = await _read_page_with_budget("http://cached.com", cache, 0, 5)

        assert status == "cached"
        assert content == "cached content"
        assert new_count == 0

    async def test_fetch_consumes_one_budget_slot_and_populates_cache(self):
        from app.core.agent_engine import _read_page_with_budget
        cache = FetchCache()

        with patch("app.core.web_fetch.web_fetcher.fetch_page", new=AsyncMock(return_value="fresh content")):
            content, new_count, status = await _read_page_with_budget("http://new.com", cache, 0, 5)

        assert status == "fetched"
        assert content == "fresh content"
        assert new_count == 1
        assert cache.get("http://new.com") == "fresh content"

    async def test_budget_exhausted_does_not_fetch(self):
        from app.core.agent_engine import _read_page_with_budget
        cache = FetchCache()

        with patch("app.core.web_fetch.web_fetcher.fetch_page", new=AsyncMock(side_effect=AssertionError("should not fetch"))):
            content, new_count, status = await _read_page_with_budget("http://over-budget.com", cache, 1, 1)

        assert status == "budget_exhausted"
        assert content is None
        assert new_count == 1

    async def test_fetch_error_is_reported_without_consuming_budget(self):
        from app.core.agent_engine import _read_page_with_budget
        cache = FetchCache()

        with patch("app.core.web_fetch.web_fetcher.fetch_page", new=AsyncMock(side_effect=RuntimeError("boom"))):
            content, new_count, status = await _read_page_with_budget("http://broken.com", cache, 0, 5)

        assert status == "error"
        assert "boom" in content
        assert new_count == 0

class TestRunAgentStateful:
    """Tests for the stateful session capabilities of run_agent."""

    async def test_run_agent_with_history_preserves_messages(self):
        """When history is provided, run_agent should use it and return the extended history."""
        history = [
            {"role": "system", "content": "Old System"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content="Final Answer", tool_calls=[submit_tc])

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=(response, "mock-model", "mock-key"))) as mock_router:
            result, final_history = await run_agent(
                agent_name="TEST",
                system_prompt="New System",
                user_prompt="Submit now",
                step="step1",
                run_id="run-stateful",
                tools_names=[],
                submit_tool_name="submitFindings",
                history=history
            )
        
        assert result == "Final Answer"
        # Check that router was called with the combined history
        called_messages = mock_router.call_args[1]["messages"]
        assert called_messages[0]["role"] == "system"
        assert called_messages[0]["content"] == "New System"
        assert called_messages[1]["content"] == "Hello"
        assert called_messages[2]["content"] == "Hi there!"
        assert called_messages[3]["role"] == "user"
        assert called_messages[3]["content"] == "Submit now"
        
        # Check that the returned history includes everything
        assert len(final_history) > len(history)
        assert final_history[0]["content"] == "New System"

    async def test_run_agent_without_history_starts_fresh(self):
        """Without history, run_agent should start with system and user prompts."""
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content="Final Answer", tool_calls=[submit_tc])

        with patch("app.core.agent_engine.router.run_model", new=AsyncMock(return_value=(response, "mock-model", "mock-key"))) as mock_router:
            result, final_history = await run_agent(
                agent_name="TEST",
                system_prompt="Sys",
                user_prompt="User",
                step="step1",
                run_id="run-fresh",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        
        called_messages = mock_router.call_args[1]["messages"]
        assert len(called_messages) == 2
        assert called_messages[0]["content"] == "Sys"
        assert called_messages[1]["content"] == "User"
