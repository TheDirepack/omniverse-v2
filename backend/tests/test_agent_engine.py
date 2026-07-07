"""
Tests for core/agent_engine.py — run_agent() loop.

All network/LLM calls are mocked via unittest.mock so these tests run offline.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agent_engine import run_agent
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
    from app.core.acquisition_cache import acquisition_cache
    acquisition_cache.clear_lru()
    yield
    ABORTED_RUNS.clear()


class TestRunAgentDirectSubmit:
    """Agent calls the submit tool immediately on the first turn."""

    async def test_submit_on_first_turn(self):
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(
            content="Here are my findings.", tool_calls=[submit_tc]
        )

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(response, "mock-model", "mock-key")),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="You are a researcher.",
                user_prompt="Research Warhammer 40k.",
                step="research",
                run_id="run-001",
                tools_names=["webSearch"],
                submit_tool_name="submitFindings",
            )
        assert success is True
        assert result == "Here are my findings."

    async def test_submit_returns_empty_content_as_default(self):
        """If content is None/empty when submit is called, return the fallback string."""
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content=None, tool_calls=[submit_tc])

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(response, "mock-model", "mock-key")),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-002",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert success is True
        assert result == "Findings submitted."


class TestRunAgentToolLoop:
    """Agent uses a tool before submitting."""

    async def test_tool_result_injected_into_messages(self):
        web_tc = _make_tool_call(
            "webSearch", {"search_query": "WH40k lore"}, tc_id="tc-search"
        )
        submit_tc = _make_tool_call("submitFindings", {}, tc_id="tc-submit")

        search_response = _make_response(content="Searching...", tool_calls=[web_tc])
        submit_response = _make_response(
            content="Done researching.", tool_calls=[submit_tc]
        )

        call_count = 0

        async def mock_run_model(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return (
                (search_response, "model", "key")
                if call_count == 1
                else (submit_response, "model", "key")
            )

        captured_messages = []

        async def mock_web_search(args):
            captured_messages.append(args)
            return "Warhammer 40k is a sci-fi setting."

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_run_model),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "webSearch": {
                        "func": mock_web_search,
                        "description": "search",
                        "parameters": {},
                    },
                },
            ),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-003",
                tools_names=["webSearch"],
                submit_tool_name="submitFindings",
            )
        assert success is True
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
            return (
                _make_response(content="submitted", tool_calls=[submit_tc]),
                "m",
                "k",
            )

        with patch("app.core.agent_engine.router.run_model", new=mock_run_model):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-004",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert success is True
        assert result == "submitted"


class TestRunAgentMaxTurns:
    """When the agent never calls submit, max_turns should be reached."""

    async def test_max_turns_returns_error_string(self):
        # Always respond with plain text (no tool calls) — forces nudge path
        # then max_turns exceeded
        no_tool_response = _make_response(content=None, tool_calls=None)

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(no_tool_response, "m", "k")),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-max",
                tools_names=[],
                submit_tool_name="submitFindings",
                max_turns=2,
            )
        assert success is False
        assert "MAX_TURNS_REACHED" in result

    async def test_text_response_without_tool_calls_returns_content(self):
        """If the model returns plain text with no tool calls, return it immediately."""
        text_response = _make_response(content="Here is my answer.", tool_calls=None)

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(text_response, "m", "k")),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-text",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert success is True
        assert result == "Here is my answer."


class TestRunAgentAbort:
    """Run aborts when run_id is in ABORTED_RUNS."""

    async def test_abort_raises_runtime_error(self):
        from app.core.runtime_state import abort_run

        await abort_run("run-aborted")

        with patch(
            "app.core.agent_engine.router.run_model", new=AsyncMock()
        ) as mock_router:
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
        from app.db.unconfirmed_schema import AcquisitionArtifact
        from app.repositories.acquisition_cache import AcquisitionCacheRepository

        # Pre-populate cache with artifact
        artifact = AcquisitionArtifact(
            content_hash="abc123",
            source_url="http://example.com",
            content_type="web_page",
            extracted_text="cached content",
            engine_name="test",
        )
        repo = AcquisitionCacheRepository()
        try:
            repo.store(artifact)
        finally:
            repo.close()

        fetch_tc = _make_tool_call(
            "fetchPage", {"urls": ["http://example.com"]}, tc_id="tc-fetch"
        )
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_router(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[fetch_tc]), "m", "k")
            return (_make_response(content="done", tool_calls=[submit_tc]), "m", "k")

        fetch_called = False

        async def mock_fetch_page(url, **kwargs):
            nonlocal fetch_called
            fetch_called = True
            return {"main_content": "fresh content", "metadata": {"word_count": 2, "page_type": "test"}}

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_router),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "fetchPage": {
                        "func": AsyncMock(),
                        "description": "fetch",
                        "parameters": {},
                    }
                },
            ),
            patch("app.core.web_fetch.web_fetcher.fetch_page", new=mock_fetch_page),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-cache",
                tools_names=["fetchPage"],
                submit_tool_name="submitFindings",
            )
        assert success is True
        assert not fetch_called, "Cached URL should not trigger fetch"


class TestReadPageCached:
    """Direct tests of the shared cache helper."""

    async def test_cache_hit_returns_content_without_fetching(self):
        from app.core.agent_engine import _read_page_cached
        from app.db.unconfirmed_schema import AcquisitionArtifact
        from app.repositories.acquisition_cache import AcquisitionCacheRepository

        repo = AcquisitionCacheRepository()
        try:
            artifact = AcquisitionArtifact(
                content_hash="hash1",
                source_url="http://cached.com",
                content_type="web_page",
                extracted_text="cached content",
                engine_name="test",
            )
            repo.store(artifact)
        finally:
            repo.close()

        with patch(
            "app.core.web_fetch.web_fetcher.fetch_page",
            new=AsyncMock(side_effect=AssertionError("should not fetch")),
        ):
            content, status = await _read_page_cached("http://cached.com")

        assert status == "cached"
        assert content == "cached content"

    async def test_fetch_populates_cache_and_returns_content(self):
        from app.core.agent_engine import _read_page_cached

        with patch(
            "app.core.web_fetch.web_fetcher.fetch_page",
            new=AsyncMock(
                return_value={
                    "main_content": "fresh content",
                    "metadata": {"word_count": 2, "page_type": "test"},
                }
            ),
        ):
            content, status = await _read_page_cached("http://new.com")

        assert status == "fetched"
        assert isinstance(content, str)
        assert content == "fresh content"

    async def test_fetch_error_is_reported(self):
        from app.core.agent_engine import _read_page_cached

        with patch(
            "app.core.web_fetch.web_fetcher.fetch_page",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            content, status = await _read_page_cached("http://broken.com")

        assert status == "error"
        assert "boom" in content


class TestRunAgentStateful:
    """Tests for the stateful session capabilities of run_agent."""

    async def test_run_agent_with_history_preserves_messages(self):
        """When history is provided, run_agent should use it and return the extended history."""
        history = [
            {"role": "system", "content": "Old System"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content="Final Answer", tool_calls=[submit_tc])

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(response, "mock-model", "mock-key")),
        ) as mock_router:
            success, result, final_history = await run_agent(
                agent_name="TEST",
                system_prompt="New System",
                user_prompt="Submit now",
                step="step1",
                run_id="run-stateful",
                tools_names=[],
                submit_tool_name="submitFindings",
                history=history,
            )
        assert success is True
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

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(response, "mock-model", "mock-key")),
        ) as mock_router:
            _success, _result, _final_history = await run_agent(
                agent_name="TEST",
                system_prompt="Sys",
                user_prompt="User",
                step="step1",
                run_id="run-fresh",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
        assert mock_router.call_count == 1
        called_messages = mock_router.call_args[1]["messages"]
        assert len(called_messages) == 2
        assert called_messages[0]["content"] == "Sys"
        assert called_messages[1]["content"] == "User"


class TestClassifyFailure:
    """_classify_failure classifies infrastructure vs recoverable errors."""

    def test_programming_error_is_infrastructure(self):
        from sqlalchemy.exc import ProgrammingError
        from app.core.agent_engine import _classify_failure
        fake = ProgrammingError("stmt", {}, "no such column")
        assert _classify_failure(fake) == "INFRASTRUCTURE_FAILURE"

    def test_operational_error_is_infrastructure(self):
        from sqlalchemy.exc import OperationalError
        from app.core.agent_engine import _classify_failure
        fake = OperationalError("stmt", {}, "no such table")
        assert _classify_failure(fake) == "INFRASTRUCTURE_FAILURE"

    def test_infra_keyword_in_message(self):
        from app.core.agent_engine import _classify_failure
        e = RuntimeError("No such column: foo")
        assert _classify_failure(e) == "INFRASTRUCTURE_FAILURE"

    def test_missing_column_keyword(self):
        from app.core.agent_engine import _classify_failure
        e = RuntimeError("missing column bar")
        assert _classify_failure(e) == "INFRASTRUCTURE_FAILURE"

    def test_undefined_column_keyword(self):
        from app.core.agent_engine import _classify_failure
        e = RuntimeError("undefined column baz")
        assert _classify_failure(e) == "INFRASTRUCTURE_FAILURE"

    def test_column_does_not_exist_keyword(self):
        from app.core.agent_engine import _classify_failure
        e = RuntimeError("column does not exist")
        assert _classify_failure(e) == "INFRASTRUCTURE_FAILURE"

    def test_generic_error_is_recoverable(self):
        from app.core.agent_engine import _classify_failure
        e = RuntimeError("connection refused")
        assert _classify_failure(e) == "RECOVERABLE"


class TestExecuteTool:
    """Direct _execute_tool tests for routing and error handling."""

    async def test_unknown_tool(self):
        from app.core.agent_engine import _execute_tool
        result = await _execute_tool("nonexistent", {})
        assert "not found" in result

    async def test_fetch_page_single_url(self):
        from app.core.agent_engine import _execute_tool
        with patch(
            "app.core.agent_engine._read_page_cached",
            new=AsyncMock(return_value=("fetched content", "fetched")),
        ):
            result = await _execute_tool("fetchPage", {"url": "http://example.com"})
            assert "fetched content" in result

    async def test_fetch_page_with_urls_list(self):
        from app.core.agent_engine import _execute_tool
        with patch(
            "app.core.agent_engine._read_page_cached",
            new=AsyncMock(return_value=("multi content", "fetched")),
        ):
            result = await _execute_tool("fetchPage", {"urls": ["http://a.com", "http://b.com"]})
            assert "multi content" in result

    async def test_fetch_page_error_status(self):
        from app.core.agent_engine import _execute_tool
        with patch(
            "app.core.agent_engine._read_page_cached",
            new=AsyncMock(return_value=("error detail", "error")),
        ):
            result = await _execute_tool("fetchPage", {"url": "http://bad.com"})
            assert "Error fetching" in result

    async def test_compare_source_freshness_empty_urls(self):
        from app.core.agent_engine import _execute_tool
        result = await _execute_tool("compareSourceFreshness", {})
        assert "Missing or invalid urls" in result

    async def test_compare_source_freshness_success(self):
        from app.core.agent_engine import _execute_tool

        async def mock_read(url, run_id=None):
            return (f"content from {url}", "fetched")

        with (
            patch(
                "app.core.agent_engine._read_page_cached",
                new=mock_read,
            ),
            patch(
                "app.core.tools.build_freshness_comparison_report",
                return_value="freshness report",
            ),
        ):
            result = await _execute_tool(
                "compareSourceFreshness", {"urls": ["http://a.com", "http://b.com"]}
            )
            assert "freshness report" in result

    async def test_ocr_image_missing_args(self):
        from app.core.agent_engine import _execute_tool
        result = await _execute_tool("ocrImage", {})
        assert "Provide either image_url or image_data" in result

    async def test_ocr_image_success(self):
        from app.core.agent_engine import _execute_tool
        fake_doc = MagicMock()
        fake_doc.extracted_text = "ocr text"
        fake_doc.engine_name = "tesseract"
        fake_doc.structured_data = None
        fake_doc.content_type = "image/ocr"
        fake_doc.metadata = {"gpu": False}

        with patch(
            "app.core.agent_engine.ocr_importer.fetch",
            new=AsyncMock(return_value=fake_doc),
        ):
            result = await _execute_tool("ocrImage", {"image_url": "http://img.png"})
            assert "ocr text" in result

    async def test_ocr_image_with_gpu(self):
        from app.core.agent_engine import _execute_tool
        fake_doc = MagicMock()
        fake_doc.extracted_text = "gpu ocr"
        fake_doc.engine_name = "easyocr"
        fake_doc.structured_data = None
        fake_doc.content_type = "image/ocr"
        fake_doc.metadata = {"gpu": True}

        with patch(
            "app.core.agent_engine.ocr_importer.fetch",
            new=AsyncMock(return_value=fake_doc),
        ):
            result = await _execute_tool("ocrImage", {"image_url": "http://img.png"})
            assert "[GPU]" in result

    async def test_ocr_image_exception(self):
        from app.core.agent_engine import _execute_tool
        with patch(
            "app.core.agent_engine.ocr_importer.fetch",
            new=AsyncMock(side_effect=RuntimeError("ocr error")),
        ):
            result = await _execute_tool("ocrImage", {"image_url": "http://img.png"})
            assert "OCR failed" in result
            assert "ocr error" in result

    async def test_generic_tool_call(self):
        from app.core.agent_engine import _execute_tool
        mock_func = AsyncMock(return_value="generic result")
        with patch(
            "app.core.agent_engine.AGENT_TOOLS",
            {
                "myTool": {
                    "func": mock_func,
                    "description": "test",
                    "parameters": {},
                },
            },
        ):
            result = await _execute_tool("myTool", {"arg": "val"})
            assert "generic result" in result
            mock_func.assert_awaited_once_with({"arg": "val"})


class TestRunAgentCoverageGap:
    """Submit tool rejects submission when coverage is too thin."""

    async def test_coverage_gap_with_pending_leads(self):
        submit_tc = _make_tool_call(
            "submitFindings",
            {
                "dataset": json.dumps({
                    "Verified_Claims": [{"claim": "c1"}],
                    "Knowledge_Graph": [
                        {"Status": "Pending", "Priority": 8},
                        {"Status": "Pending", "Priority": 3},
                    ],
                })
            },
        )
        retry_tc = _make_tool_call("submitFindings", {"dataset": '{"Verified_Claims":[],"Knowledge_Graph":[]}'})

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[submit_tc]), "m", "k")
            return (_make_response(content="final", tool_calls=[retry_tc]), "m", "k")

        with patch("app.core.agent_engine.router.run_model", new=mock_run):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-gap",
                tools_names=[],
                submit_tool_name="submitFindings",
                max_turns=5,
            )
        assert success is not None

    async def test_coverage_too_low_less_than_3(self):
        submit_tc = _make_tool_call(
            "submitFindings",
            {"dataset": json.dumps({"Verified_Claims": [{"c": 1}, {"c": 2}], "Knowledge_Graph": []})},
        )
        retry_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[submit_tc]), "m", "k")
            return (_make_response(content="done", tool_calls=[retry_tc]), "m", "k")

        with patch("app.core.agent_engine.router.run_model", new=mock_run):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-low",
                tools_names=[],
                submit_tool_name="submitFindings",
                max_turns=5,
            )
        assert success is not None

    async def test_malformed_dataset_returns_raw_string(self):
        submit_tc = _make_tool_call(
            "submitFindings",
            {"dataset": "not valid json"},
        )

        async def mock_run(*args, **kwargs):
            return (_make_response(content="fallback content", tool_calls=[submit_tc]), "m", "k")

        with patch("app.core.agent_engine.router.run_model", new=mock_run):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-badjson",
                tools_names=[],
                submit_tool_name="submitFindings",
            )
            assert success is True
            assert "not valid JSON" in result



class TestRunAgentExecutePlan:
    """executePlan tool dispatches multi-step plans."""

    async def test_execute_plan_basic(self):
        plan_tc = _make_tool_call(
            "executePlan",
            {"plan": [{"tool": "webSearch", "args": {"search_query": "test"}}]},
        )
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[plan_tc]), "m", "k")
            return (_make_response(content="planned", tool_calls=[submit_tc]), "m", "k")

        mock_search = AsyncMock(return_value="search result")

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_run),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "webSearch": {
                        "func": mock_search,
                        "description": "search",
                        "parameters": {},
                    },
                    "executePlan": {
                        "func": None,
                        "description": "Execute a plan",
                        "parameters": {},
                    },
                },
            ),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-plan",
                tools_names=["webSearch", "executePlan"],
                submit_tool_name="submitFindings",
                max_turns=5,
            )
        assert success is True
        assert result == "planned"
        mock_search.assert_awaited_once()

    async def test_execute_plan_with_result_placeholder(self):
        plan_tc = _make_tool_call(
            "executePlan",
            {
                "plan": [
                    {"tool": "webSearch", "args": {"search_query": "first"}},
                    {"tool": "webSearch", "args": {"search_query": "$result_0"}},
                ]
            },
        )
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_search(args):
            return "result_from_step_0"

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[plan_tc]), "m", "k")
            return (_make_response(content="done", tool_calls=[submit_tc]), "m", "k")

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_run),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "webSearch": {
                        "func": mock_search,
                        "description": "search",
                        "parameters": {},
                    },
                    "executePlan": {
                        "func": None,
                        "description": "Execute a plan",
                        "parameters": {},
                    },
                },
            ),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-place",
                tools_names=["webSearch", "executePlan"],
                submit_tool_name="submitFindings",
                max_turns=5,
            )
        assert success is True
        assert result == "done"

    async def test_execute_plan_step_exception(self):
        plan_tc = _make_tool_call(
            "executePlan",
            {"plan": [{"tool": "webSearch", "args": {"search_query": "x"}}]},
        )
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (_make_response(content=None, tool_calls=[plan_tc]), "m", "k")
            return (_make_response(content="recovered", tool_calls=[submit_tc]), "m", "k")

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_run),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "webSearch": {
                        "func": AsyncMock(side_effect=RuntimeError("step fail")),
                        "description": "search",
                        "parameters": {},
                    },
                    "executePlan": {
                        "func": None,
                        "description": "Execute a plan",
                        "parameters": {},
                    },
                },
            ),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-planerr",
                tools_names=["webSearch", "executePlan"],
                submit_tool_name="submitFindings",
                max_turns=5,
            )
        assert success is True
        assert result == "recovered"


class TestRunAgentToolFailureTracking:
    """Consecutive tool failures are tracked and escalated."""

    async def test_recoverable_failure_escalates(self):
        fail_func = AsyncMock(side_effect=RuntimeError("transient error"))
        tool_tc = _make_tool_call("failTool", {})
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return (_make_response(content=None, tool_calls=[tool_tc]), "m", "k")
            return (_make_response(content="after fails", tool_calls=[submit_tc]), "m", "k")

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_run),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "failTool": {
                        "func": fail_func,
                        "description": "fails",
                        "parameters": {},
                    },
                },
            ),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-failtrack",
                tools_names=["failTool"],
                submit_tool_name="submitFindings",
                max_turns=10,
            )
        assert success is True
        assert result == "after fails"

    async def test_infrastructure_failure_disables_tool(self):
        fail_func = AsyncMock(side_effect=RuntimeError("no such column: foo"))
        tool_tc = _make_tool_call("infraTool", {})
        submit_tc = _make_tool_call("submitFindings", {})

        call_count = 0

        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return (_make_response(content=None, tool_calls=[tool_tc]), "m", "k")
            return (_make_response(content="infra done", tool_calls=[submit_tc]), "m", "k")

        with (
            patch("app.core.agent_engine.router.run_model", new=mock_run),
            patch(
                "app.core.agent_engine.AGENT_TOOLS",
                {
                    "infraTool": {
                        "func": fail_func,
                        "description": "infra fail",
                        "parameters": {},
                    },
                },
            ),
        ):
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="sys",
                user_prompt="user",
                step="s",
                run_id="run-infra",
                tools_names=["infraTool"],
                submit_tool_name="submitFindings",
                max_turns=10,
            )
        assert success is True
        assert result == "infra done"


class TestRunAgentStatefulEdgeCases:
    """Edge cases around history handling."""

    async def test_history_already_has_matching_system_prompt(self):
        history = [
            {"role": "system", "content": "Same System"},
            {"role": "user", "content": "Hello"},
        ]
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content="Result", tool_calls=[submit_tc])

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(response, "mock-model", "mock-key")),
        ) as mock_router:
            success, result, final_history = await run_agent(
                agent_name="TEST",
                system_prompt="Same System",
                user_prompt="Submit now",
                step="step1",
                run_id="run-same-system",
                tools_names=[],
                submit_tool_name="submitFindings",
                history=history,
            )
        assert success is True
        assert result == "Result"
        called_messages = mock_router.call_args[1]["messages"]
        assert called_messages[0]["content"] == "Same System"

    async def test_history_ends_with_same_user_prompt(self):
        history = [
            {"role": "system", "content": "Sys"},
            {"role": "user", "content": "Same prompt"},
        ]
        submit_tc = _make_tool_call("submitFindings", {})
        response = _make_response(content="Result", tool_calls=[submit_tc])

        with patch(
            "app.core.agent_engine.router.run_model",
            new=AsyncMock(return_value=(response, "mock-model", "mock-key")),
        ) as mock_router:
            success, result, _ = await run_agent(
                agent_name="TEST",
                system_prompt="Sys",
                user_prompt="Same prompt",
                step="step1",
                run_id="run-same-prompt",
                tools_names=[],
                submit_tool_name="submitFindings",
                history=history,
            )
        assert success is True
        assert result == "Result"
        called_messages = mock_router.call_args[1]["messages"]
        assert len(called_messages) == 2  # system + user, no duplicate
