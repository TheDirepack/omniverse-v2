import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.agent_engine import run_agent, context_manager
from app.core.runtime_state import set_current_summary, get_current_summary, set_current_run_id
from app.services.settings_service import SettingsService


@pytest.fixture
def mock_settings_service():
    with patch("app.services.settings_service.SettingsService", autospec=True) as mock:
        instance = mock.return_value
        instance.get_all_settings.return_value = {
            "general_settings": {
                "MAX_TOKENS": "1000",
                "COMPRESSION_THRESHOLD": "0.5",
            }
        }
        yield instance


@pytest.fixture
def mock_router():
    with patch("app.core.agent_engine.router", autospec=True) as mock:
        # Default response for run_model
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Standard Response"
        mock.run_model.return_value = (mock_response, "gpt-4o", "key-1")
        yield mock


@pytest.mark.asyncio
async def test_context_manager_reconfigure():
    cm = context_manager
    cm.reconfigure(500, 0.7)
    assert cm.max_tokens == 500
    assert cm.summary_threshold == 0.7


@pytest.mark.asyncio
async def test_run_agent_uses_settings(mock_settings_service, mock_router):
    # Force a low threshold so we can test compression
    mock_settings_service.get_all_settings.return_value = {
        "general_settings": {
            "MAX_TOKENS": "100",
            "COMPRESSION_THRESHOLD": "0.1",
        }
    }
    
    # We'll need to mock count_tokens to return a value > 10 (100 * 0.1)
    with patch.object(context_manager, 'count_tokens', return_value=20):
        # Mock compress_context to avoid real LLM call
        mock_response_empty = MagicMock()
        mock_response_empty.choices = [MagicMock()]
        mock_response_empty.choices[0].message.content = ""
        
        mock_response_final = MagicMock()
        mock_response_final.choices = [MagicMock()]
        mock_response_final.choices[0].message.content = "Final Answer"
        
        mock_router.run_model.side_effect = [
            (mock_response_empty, "gpt-4o", "key-1"),
            (mock_response_final, "gpt-4o", "key-1")
        ]

        with patch.object(context_manager, 'compress_context', new_callable=AsyncMock) as mock_compress:
            mock_compress.return_value = ([{"role": "system", "content": "new system"}], "Summary content")

            await run_agent(
                agent_name="TestAgent",
                system_prompt="System",
                user_prompt="User",
                step="Test",
                run_id="test-run",
                tools_names=[],
                submit_tool_name="submit"
            )

            assert context_manager.max_tokens == 100
            assert context_manager.summary_threshold == 0.1
            assert mock_compress.called


@pytest.mark.asyncio
async def test_run_agent_triggers_compression_on_notebook_write(mock_settings_service, mock_router):
    mock_settings_service.get_all_settings.return_value = {
        "general_settings": {
            "MAX_TOKENS": "1000",
            "COMPRESSION_THRESHOLD": "0.5",
        }
    }
    
    # Mock count_tokens to trigger compression
    with patch.object(context_manager, 'count_tokens', return_value=600):
        # Mock compress_context
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summarized context"
        
        # Add a tool call to the mock response
        tool_call = MagicMock()
        tool_call.function.name = "saveNotebookEntry"
        tool_call.function.arguments = json.dumps({"title": "Test", "summary": "Test summary"})
        tool_call.id = "call_123"
        tool_call.type = "function"
        mock_response.choices[0].message.tool_calls = [tool_call]
        
        mock_router.run_model.return_value = (mock_response, "gpt-4o", "key-1")
    
        with patch.object(context_manager, 'compress_context', new_callable=AsyncMock) as mock_compress:
            mock_compress.return_value = ([{"role": "assistant", "content": "done"}], "Summarized context")
    
            # We need to mock the actual tool function inside AGENT_TOOLS
            async def mock_tool_func(args):
                return "Notebook entry saved successfully."
    
            with patch.dict("app.core.tools.AGENT_TOOLS", {
                "saveNotebookEntry": {
                    "func": mock_tool_func,
                    "description": "Saves a notebook entry.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["title", "summary"],
                    },
                }
            }, clear=False):
                await run_agent(
                    agent_name="Researcher",
                    system_prompt="You are a researcher. Always save your findings to the notebook.",
                    user_prompt="Research the moon.",
                    step="Test Notebook Write",
                    run_id="test-notebook-run",
                    tools_names=["saveNotebookEntry"],
                    submit_tool_name="submit"
                )
                
                assert mock_compress.called
                assert get_current_summary() == "Summarized context"


@pytest.mark.asyncio
async def test_run_agent_resumption_injects_summary(mock_settings_service, mock_router):
    mock_settings_service.get_all_settings.return_value = {
        "general_settings": {
            "MAX_TOKENS": "32000",
            "COMPRESSION_THRESHOLD": "0.8",
        }
    }
    
    summary = "This is a saved summary from a previous session."
    set_current_run_id("resume-run")
    set_current_summary(summary)
    
    # We expect the summary to be injected as a system message.
    # We can check if the tool call or model call receives it.
    
    # Mock run_model to inspect the messages it receives
    async def side_effect(task, messages, tools=None, run_id=None, provider_id=None):
        # Check if summary is in messages
        summary_in_messages = any(
            m.get("role") == "system" and summary in m.get("content", "")
            for m in messages
        )
        if not summary_in_messages:
            raise ValueError("Summary not found in messages!")
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        return (mock_response, "gpt-4o", "key-1")

    mock_router.run_model.side_effect = side_effect
    
    await run_agent(
        agent_name="TestAgent",
        system_prompt="System",
        user_prompt="User",
        step="Test Resumption",
        run_id="resume-run",
        tools_names=[],
        submit_tool_name="submit"
    )
