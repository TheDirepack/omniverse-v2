import asyncio
import re
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from app.core.router import router
from app.core.tools import AGENT_TOOLS

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

async def run_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    step: str,
    run_id: str,
    tools_names: List[str],
    submit_tool_name: str,
    max_turns: int = 6,
    max_fetches: int = 5,
    provider_id: Optional[int] = None
) -> Tuple[str, Optional[str]]:
    """
    Runs a tool-using agent loop.
    Returns (final_answer, discovered_domain).
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Filter tools and prepare litellm-compatible tool definitions
    available_tools = {k: v for k, v in AGENT_TOOLS.items() if k in tools_names}
    litellm_tools = []
    for name, info in available_tools.items():
        litellm_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_query": {"type": "string"},
                        "urls": {"type": "array", "items": {"type": "string"}},
                        "url": {"type": "string"},
                        "entity": {"type": "string"},
                        "query": {"type": "string"}
                    },
                    "required": [] # Dynamic based on tool
                }
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
    discovered_domain = None

    for turn in range(max_turns):
        response = await router.call_llm_with_tools(
            task=agent_name,
            messages=messages,
            tools=litellm_tools,
            provider_id=provider_id
        )

        # litellm response usually has tool_calls in the message
        message = response.choices[0].message
        content = message.content
        tool_calls = getattr(message, "tool_calls", None)

        if tool_calls:
            for tool_call in tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if name == submit_tool_name:
                    return content or "Findings submitted.", discovered_domain

                if name in available_tools:
                    # Handle fetch budget and cache
                    if name == "fetchPage":
                        urls = args.get("urls", []) if isinstance(args.get("urls"), list) else [args.get("url")]
                        urls = [u for u in urls if u]
                        
                        results = []
                        for url in urls:
                            if discovered_domain is None:
                                discovered_domain = urlparse(url).netloc
                            
                            cached = run_fetch_cache.get(url)
                            if cached:
                                results.append(f"Cached content for {url}:\n{cached}")
                            elif fetched_count < max_fetches:
                                try:
                                    from app.core.web_fetch import web_fetcher
                                    content = await web_fetcher.fetch_page(url)
                                    run_fetch_cache.set(url, content)
                                    results.append(f"Fetched content for {url}:\n{content}")
                                    fetched_count += 1
                                except Exception as e:
                                    results.append(f"Error fetching {url}: {str(e)}")
                            else:
                                results.append(f"Fetch budget exhausted for {url}.")
                        observation = "\n\n".join(results)
                    else:
                        # Other tools (e.g. search)
                        try:
                            from app.core.tools import AGENT_TOOLS
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
        
        return content, discovered_domain

    return "Error: Max turns reached without submission.", discovered_domain
