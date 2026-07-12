import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.agent_engine import run_agent
from app.core.agent_event_types import AgentEventType


@pytest.mark.asyncio
async def test_execute_plan_logs_steps():
    """Verify that executePlan logs granular STEP events for each plan item."""

    # Setup mock responses
    mock_response = MagicMock()

    # Agent decides to use executePlan
    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.type = "function"
    tool_call.function = MagicMock()
    tool_call.function.name = "executePlan"
    tool_call.function.arguments = json.dumps({
                        "plan": [
                            {"tool": "queryClaims", "args": {"subject": "Test"}},
                            {
                                "tool": "upsertClaims",
                                 "args": {
                                     "subject": "Test",
                                     "predicate": "is",
                                     "object_val": "True",
                                 },
                            },
                        ]

    })

    mock_message = MagicMock()
    mock_message.content = None
    mock_message.tool_calls = [tool_call]
    mock_response.choices = [MagicMock(message=mock_message)]

    # Mock the router and logger
    with (
        patch(
            "app.core.router.router.run_model",
            new_callable=AsyncMock,
        ) as mock_run_model,
        patch("app.core.agent_engine.agent_logger.log") as mock_log,
        patch(
            "app.core.agent_engine._execute_tool",
            new_callable=AsyncMock,
        ) as mock_exec_tool,
    ):

        mock_run_model.return_value = (mock_response, "gpt-4", "key-123")
        mock_exec_tool.return_value = "Success"

        # We need to stop the agent from looping forever or calling submit
        # The agent will call executePlan, then it will get the result.
        # On the second turn, we'll make it submit.

        submit_tool_call = MagicMock()
        submit_tool_call.id = "call_2"
        submit_tool_call.type = "function"
        submit_tool_call.function = MagicMock()
        submit_tool_call.function.name = "submit"
        submit_tool_call.function.arguments = "{}"

        submit_message = MagicMock()
        submit_message.content = None
        submit_message.tool_calls = [submit_tool_call]

        submit_response = MagicMock()
        submit_response.choices = [MagicMock(message=submit_message)]

        mock_run_model.side_effect = [
            (mock_response, "gpt-4", "key-123"),
            (submit_response, "gpt-4", "key-123"),
        ]

        await run_agent(
            agent_name="TestAgent",
            system_prompt="System",
            user_prompt="User",
            step="Step1",
            run_id="run-123",
            tools_names=["queryClaims", "upsertClaims", "executePlan"],
            submit_tool_name="submit",
            max_turns=2,
            min_turns=0,
        )

        # Verify that agent_logger.log was called with AgentEventType.STEP
        step_logs = [
            call for call in mock_log.call_args_list
            if call.kwargs.get("event_type") == AgentEventType.STEP
        ]

        assert len(step_logs) == 2, f"Expected 2 STEP logs, found {len(step_logs)}"

        # Check first step content
        first_step_content = step_logs[0].kwargs.get("content")
        assert "Executing step 1/2: queryClaims" in first_step_content

        # Check second step content
        second_step_content = step_logs[1].kwargs.get("content")
        assert "Executing step 2/2: upsertClaims" in second_step_content

        # Verify model and key_id were passed correctly
        assert step_logs[0].kwargs.get("model") == "gpt-4"
        assert step_logs[0].kwargs.get("key_id") == "key-123"

