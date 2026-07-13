import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.core.context_manager import ContextManager

@pytest.fixture
def cm():
    return ContextManager(max_tokens=100, summary_threshold=0.5)

def test_count_tokens_approximation(cm):
    # Mock litellm to force fallback
    import litellm
    original_counter = litellm.token_counter
    litellm.token_counter = MagicMock(side_effect=Exception("Error"))
    
    messages = [{"role": "user", "content": "Hello world"}] # 11 chars
    # 11 // 4 = 2
    assert cm.count_tokens(messages, "gpt-4o") == 2
    
    litellm.token_counter = original_counter

def test_truncate_observation(cm):
    long_text = "a" * 20000
    truncated = cm.truncate_observation(long_text, max_length=100)
    assert len(truncated) < 20000
    assert "truncated for brevity" in truncated
    
    short_text = "Hello"
    assert cm.truncate_observation(short_text, max_length=100) == "Hello"

def test_prune_raw_observations(cm):
    messages = [
        {"role": "user", "content": "Research X"},
        {"role": "tool", "name": "fetchPage", "content": "Raw content 1"},
        {"role": "assistant", "content": "I found something"},
        {"role": "tool", "name": "fetchPage", "content": "Raw content 2"},
        {"role": "assistant", "content": "Found more"},
    ]
    
    # Prune with a writing tool
    pruned = cm.prune_raw_observations(messages, "upsertArtifacts")
    
    # fetchPage messages should be gone
    assert len(pruned) == 3
    assert all(m.get("name") != "fetchPage" for m in pruned)
    
    # Should not prune with a non-writing tool
    not_pruned = cm.prune_raw_observations(messages, "webSearch")
    assert len(not_pruned) == len(messages)

@pytest.mark.asyncio
async def test_compress_context(cm):
    # Mock router
    mock_router = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Summarized state: X is a planet."
    mock_router.run_model.return_value = (mock_response, "gpt-4o", "key-1")
    
    messages = [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "Goal: Research X"},
        {"role": "assistant", "content": "Thinking..."},
        {"role": "tool", "name": "fetchPage", "content": "Page 1 content"},
        {"role": "assistant", "content": "Thought 2"},
        {"role": "tool", "name": "fetchPage", "content": "Page 2 content"},
        {"role": "assistant", "content": "Thought 3"},
        {"role": "tool", "name": "fetchPage", "content": "Page 3 content"},
        {"role": "assistant", "content": "Thought 4"},
        {"role": "tool", "name": "fetchPage", "content": "Page 4 content"},
        {"role": "assistant", "content": "Thought 5"},
        {"role": "tool", "name": "fetchPage", "content": "Page 5 content"},
        {"role": "assistant", "content": "Recent 1"},
        {"role": "tool", "name": "fetchPage", "content": "Recent 2"},
        {"role": "assistant", "content": "Recent 3"},
        {"role": "tool", "name": "fetchPage", "content": "Recent 4"},
        {"role": "assistant", "content": "Recent 5"},
    ]
    
    compressed = await cm.compress_context(
        messages=messages,
        model="gpt-4o",
        router_instance=mock_router,
        system_prompt="System prompt",
        user_goal="Goal: Research X"
    )
    
    # Should have: System + Goal + Summary + 5 recent messages = 8 messages
    assert len(compressed) == 8
    assert compressed[0]["role"] == "system"
    assert compressed[1]["role"] == "user"
    assert "Context Summary" in compressed[2]["content"]
    assert "Summarized state: X is a planet" in compressed[2]["content"]
    assert compressed[-1]["content"] == "Recent 5"
