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
            text = ""
            for m in messages:
                if "content" in m and isinstance(m["content"], str):
                    text += m["content"]
                if "tool_calls" in m and isinstance(m["tool_calls"], list):
                    for tc in m["tool_calls"]:
                        if "function" in tc:
                            text += tc["function"].get("name", "")
                            text += tc["function"].get("arguments", "")
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
            "You are a context compression engine. Produce a structured summary "
            "of the research conversation.\n\n"
            "## Objective\nWhat is the current research goal?\n\n"
            "## Completed Work\n- List verified claims, discovered facts, "
            "and what has been accomplished.\n\n"
            "## Active Leads\n- List pending investigations, unresolved "
            "questions, and their priority.\n\n"
            "## Key Sources\n- List important URLs and sources found.\n\n"
            "## Blockers\n- What is preventing progress?\n\n"
            "## Next Steps\n- What should the agent do next?\n\n"
            "Output ONLY the summary sections, no preamble."
        )

        serialized = json.dumps(to_summarize, indent=2)
        summary_messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": f"History to summarize:\n{serialized}"}
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

        # Filter recent history to avoid goal duplication
        filtered_recent = [m for m in recent_history if m is not original_goal]

        # 3. Reconstruct history
        compressed_history = [
            system_msg,
            original_goal,
            {"role": "system", "content": (
                f"Context Summary of previous turns:\n{summary_text}"
            )},
            *filtered_recent
        ]

        return compressed_history, summary_text


    def prune_old_observations(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Prune old tool outputs (not full messages) to free context space
        without an LLM call.

        Strategy (inspired by opencode):
        1. Walk backward through messages
        2. Protect the last 2 conversation turns
        3. Protect tool outputs within the last 40K tokens
        4. Replace old tool outputs with short markers
        5. Only prune if >20K tokens can be freed

        Returns: (pruned_messages, tokens_freed)
        """
        minimum_prune = 20000
        protect_tokens = 40000
        protect_turns = 2

        tokens_freed = 0
        accumulated = 0
        turn_count = 0

        writing_tools = {"saveNotebookEntry", "upsertArtifacts", "updateArtifact"}

        prunable_indices = []
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg.get("role") == "user":
                turn_count += 1
            if turn_count < protect_turns:
                continue
            if msg.get("role") == "tool" and msg.get("name") not in writing_tools:
                content = msg.get("content", "")
                estimated = len(content) // 4
                if accumulated + estimated > protect_tokens:
                    prunable_indices.append(i)
                    tokens_freed += estimated
                else:
                    accumulated += estimated

        if tokens_freed < minimum_prune:
            return messages, 0

        new_messages = list(messages)
        for i in prunable_indices:
            content = new_messages[i].get("content", "")
            original_len = len(content)
            marker = f"[Pruned: original {original_len} chars]"
            new_messages[i] = {**new_messages[i], "content": marker}

        return new_messages, tokens_freed

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
