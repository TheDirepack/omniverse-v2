import json
from typing import Any

import litellm


class ContextManager:
    def __init__(self, max_tokens: int = 32000, summary_threshold: float = 0.8):
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold

    def reconfigure(self, max_tokens: int, summary_threshold: float):
        """Update the configuration parameters."""
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold

    def count_tokens(self, messages: list[dict[str, Any]], model: str) -> int:
        """
        Count tokens in the message history using litellm.
        Returns approximate count if litellm fails.
        """
        try:
            return litellm.token_counter(messages=messages, model=model)
        except Exception:
            # Fallback approximation: 4 chars per token
            text = "".join([
                m.get("content", "") if isinstance(m.get("content"), str) else ""
                for m in messages
            ])
            return len(text) // 4

    async def compress_context(
        self,
        messages: list[dict[str, Any]],
        model: str,
        router_instance: Any,
        system_prompt: str,
        user_goal: str
    ) -> tuple[list[dict[str, Any]], str]:
        """
        Summarizes the middle of the history to free up space while preserving
        the system prompt, the original goal, and the most recent turns.
        Returns: (compressed_messages, summary_text)
        """
        if len(messages) < 10:  # Don't compress very short histories
            return messages, ""

        # 1. Identify what to preserve
        system_msg = {"role": "system", "content": system_prompt}

        # Preserve the original user goal (first user message)
        original_goal = next(
            (m for m in messages if m["role"] == "user"),
            {"role": "user", "content": user_goal}
        )

        # Preserve last 5 messages for immediate continuity
        recent_history = messages[-5:]

        # Messages to be summarized (everything between the goal and the recent window)
        # We find the index of the original goal to slice correctly
        try:
            goal_idx = messages.index(original_goal)
        except ValueError:
            goal_idx = 0

        to_summarize = messages[goal_idx + 1 : -5]
        if not to_summarize:
            return messages, ""

        # 2. Request summary from the model
        summary_prompt = (
            "You are a context compression engine. Summarize the following conversation history "
            "into a concise 'Current State Summary'. Preserve all key facts, verified claims, "
            "and the current progress of the research. Do not lose specific identifiers or "
            "crucial evidence. Output only the summary text."
        )

        summary_messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": f"History to summarize:\n{json.dumps(to_summarize, indent=2)}"}
        ]

        try:
            response, _, _ = await router_instance.run_model(
                task="context_summarization",
                messages=summary_messages,
                run_id=None,
            )
            summary_text = response.choices[0].message.content
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            print(f"Context compression failed: {e}")
            return messages, "" # Fallback to original on failure

        # 3. Reconstruct history
        compressed_history = [
            system_msg,
            original_goal,
            {"role": "system", "content": f"Context Summary of previous turns:\n{summary_text}"},
            *recent_history
        ]

        return compressed_history, summary_text


    def truncate_observation(self, content: str, max_length: int = 10000) -> str:
        """Truncate long tool observations to prevent context blowup."""
        if not content or not isinstance(content, str) or len(content) <= max_length:
            return content
        return content[:max_length] + "... [Content truncated for brevity]"

    def prune_raw_observations(self, messages: list[dict[str, Any]], tool_name: str) -> list[dict[str, Any]]:
        """
        Removes previous raw observations from the history when a writing tool is called,
        assuming the agent has now extracted the necessary information.
        """
        # Only prune if the current tool is a 'writing' tool
        writing_tools = {"upsertArtifacts", "updateArtifact", "saveNotebookEntry"}
        if tool_name not in writing_tools:
            return messages

        # We identify 'raw' observations (typically from fetchPage or webSearch)
        # and remove them from the history to save space.
        raw_tool_names = {"fetchPage", "webSearch", "ocrImage"}

        new_messages = []
        for msg in messages:
            if msg.get("role") == "tool" and msg.get("name") in raw_tool_names:
                continue # Prune this raw observation
            new_messages.append(msg)

        return new_messages
