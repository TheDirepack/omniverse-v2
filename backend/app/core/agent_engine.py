import asyncio
import re
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from app.core.router import router
from app.core.tools import AGENT_TOOLS, build_freshness_comparison_report
from app.core.agent_logger import agent_logger

class FetchCache:
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def get(self, url: str) -> Optional[str]:
        if url is None:
            raise TypeError("url must be a string, not None")
        return self._cache.get(url)

    def set(self, url: str, content: str):
        if url is None:
            raise TypeError("url must be a string, not None")
        self._cache[url] = content

    def clear(self):
        self._cache.clear()

# Global cache for the current run
# In a production environment, this would be per-run_id in Redis
run_fetch_cache = FetchCache()


async def _read_page_with_budget(url: str, cache: FetchCache, fetched_count: int, max_fetches: int):
    """
    Single choke point for reading full page content during an agent run.
    Every tool that needs page content (fetchPage, compareSourceFreshness,
    and any future one) MUST go through this so they all draw from the same
    cache and the same per-run fetch budget, instead of a tool fetching
    pages on its own and silently exceeding the budget.
    Returns (content_or_error_message, updated_fetched_count, status) where
    status is one of "cached", "fetched", "budget_exhausted", "error".
    """
    cached = cache.get(url)
    if cached:
        return cached, fetched_count, "cached"
    if fetched_count >= max_fetches:
        return None, fetched_count, "budget_exhausted"
    try:
        from app.core.web_fetch import web_fetcher
        page_content = await web_fetcher.fetch_page(url)
        cache.set(url, page_content)
        return page_content, fetched_count + 1, "fetched"
    except Exception as e:
        return str(e), fetched_count, "error"

async def run_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    step: str,
    run_id: str,
    tools_names: List[str],
    submit_tool_name: str,
    max_turns: int = 50,
    max_retries: int = 1,
    max_fetches: int = 5,
    provider_id: Optional[int] = None,
    fetch_cache: Optional[FetchCache] = None,
    history: Optional[List[Dict[str, str]]] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Runs a tool-using agent loop.
    Returns (final_answer, full_messages_history).
    """
    for attempt in range(max_retries + 1):
        if history:
            messages = list(history)
            # Ensure system prompt is current if it's the first message or needs update
            if not messages or messages[0]["role"] != "system":
                messages.insert(0, {"role": "system", "content": system_prompt})
            elif messages[0]["role"] == "system":
                messages[0]["content"] = system_prompt
            
            # If the history doesn't end with the current user prompt, add it
            if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != user_prompt:
                messages.append({"role": "user", "content": user_prompt})
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        
        # Use provided cache or fallback to global (legacy)
        cache = fetch_cache or run_fetch_cache
        
        # Filter tools and prepare litellm-compatible tool definitions
        available_tools = {k: v for k, v in AGENT_TOOLS.items() if k in tools_names}
        litellm_tools = []
        for name, info in available_tools.items():
            litellm_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"]
                }
            })
        
        # Add the submit tool
        litellm_tools.append({
            "type": "function",
            "function": {
                "name": submit_tool_name,
                "description": "Submit the final verified findings.",
                "parameters": {"type": "object", "properties": {}}
            }
        })
        
        fetched_count = 0
        
        for turn in range(max_turns):
            from app.core.runtime_state import is_aborted
            if await is_aborted(run_id):
                raise RuntimeError(f"Run {run_id} was aborted by user.")

            response, model, key_id = await router.run_model(
                task=agent_name,
                messages=messages,
                tools=litellm_tools,
                run_id=run_id,
                provider_id=provider_id
            )

            # litellm response usually has tool_calls in the message
            message = response.choices[0].message
            content = message.content
            tool_calls = getattr(message, "tool_calls", None)

            # Log agent thinking
            if content:
                agent_logger.log(
                    agent=agent_name,
                    event_type="THOUGHT",
                    content=content,
                    model=model,
                    key_id=key_id
                )

            if tool_calls:
                # Append assistant message with tool calls to history
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in tool_calls
                    ]
                })
                for tool_call in tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if name == submit_tool_name:
                        # If the tool provides a dataset, use it; otherwise, fallback to content
                        args_dataset = args.get("dataset")
                        return args_dataset or content or "Findings submitted.", messages




                    if name in available_tools:
                        # Log tool request
                        agent_logger.log(
                            agent=agent_name,
                            event_type="TOOL_REQ",
                            content=f"Calling {name} with args {json.dumps(args)}",
                            model=model,
                            key_id=key_id
                        )
                        # Handle fetch budget and cache. Any tool that needs full page
                        # content is special-cased here (rather than left to the
                        # generic branch below) so ALL page reads in a run share ONE
                        # cache and ONE fetch budget — otherwise a tool that fetches
                        # pages internally (e.g. compareSourceFreshness) could bypass
                        # the budget entirely.
                        if name == "fetchPage":
                            urls = args.get("urls", []) if isinstance(args.get("urls"), list) else [args.get("url")]
                            urls = [u for u in urls if u]

                            results = []
                            for url in urls:
                                content, fetched_count, status = await _read_page_with_budget(url, cache, fetched_count, max_fetches)
                                if status == "cached":
                                    results.append(f"Cached content for {url}:\n{content}")
                                elif status == "fetched":
                                    results.append(f"Fetched content for {url}:\n{content}")
                                elif status == "budget_exhausted":
                                    results.append(f"Fetch budget exhausted for {url}.")
                                else:
                                    results.append(f"Error fetching {url}: {content}")
                            observation = "\n\n".join(results)
                        elif name == "compareSourceFreshness":
                            urls = args.get("urls", [])
                            if not urls or not isinstance(urls, list):
                                observation = "Error: Missing or invalid urls argument (expected a list of at least 2 URLs)."
                            else:
                                url_content_map = {}
                                for url in urls:
                                    content, fetched_count, status = await _read_page_with_budget(url, cache, fetched_count, max_fetches)
                                    url_content_map[url] = content if status in ("cached", "fetched") else None
                                observation = build_freshness_comparison_report(url_content_map)
                        else:
                            # Other tools (e.g. search)
                            try:
                                func = AGENT_TOOLS[name]["func"]
                                observation = await func(args)
                            except Exception as e:
                                observation = f"Error executing tool {name}: {str(e)}"

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": observation
                        })
                        
                        # Log tool response
                        agent_logger.log(
                            agent=agent_name,
                            event_type="TOOL_RES",
                            content=f"Observation from {name}: {observation[:500]}..." if len(observation) > 500 else f"Observation from {name}: {observation}",
                            model=model,
                            key_id=key_id
                        )
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": f"Error: Tool {name} not found."
                        })
                
                # After executing tool calls, the agent needs to process observations
                continue
            
            # If no tool calls, the model might have just replied. 
            # If it's not a submit call, we nudge it to use tools or submit.
            if not content:
                messages.append({"role": "user", "content": "Please use the available tools to research and eventually call the submit tool."})
                continue
            
            return content, messages
            
        if attempt < max_retries:
            continue
        else:
            return "MAX_TURNS_REACHED", messages

    return "Error: Max turns reached without submission.", messages
