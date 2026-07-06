import json
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.exc import ProgrammingError, OperationalError
from app.core.router import router
from app.core.tools import AGENT_TOOLS
from app.core.agent_logger import agent_logger
from app.core.agent_event_types import AgentEventType

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


async def _read_page_with_budget(url: str, cache: FetchCache, fetched_count: List[int], max_fetches: int):
    """
    Single choke point for reading full page content during an agent run.
    Returns (content_or_error_message, status). fetched_count[0] is updated in-place.
    """
    cached = cache.get(url)
    if cached:
        return cached, "cached"
    if fetched_count[0] >= max_fetches:
        return None, "budget_exhausted"
    try:
        from app.core.web_fetch import web_fetcher
        page_content = await web_fetcher.fetch_page(url)
        cache.set(url, page_content)
        fetched_count[0] += 1
        return page_content, "fetched"
    except Exception as e:
        return str(e), "error"

def _classify_failure(e: Exception) -> str:
    """Classify failure as RECOVERABLE or INFRASTRUCTURE_FAILURE."""
    if isinstance(e, (ProgrammingError, OperationalError)):
        return "INFRASTRUCTURE_FAILURE"
    
    err_msg = str(e).lower()
    infra_keywords = ["no such column", "no such table", "missing column", "undefined column", "column does not exist"]
    if any(kw in err_msg for kw in infra_keywords):
        return "INFRASTRUCTURE_FAILURE"
    
    return "RECOVERABLE"

async def _execute_tool(name: str, args: Dict[str, Any], cache: FetchCache, fetched_count: List[int], max_fetches: int) -> str:
    """Executes a tool and handles budget/cache for fetchPage."""
    if name == "fetchPage":
        urls = args.get("urls", []) if isinstance(args.get("urls"), list) else [args.get("url")]
        urls = [u for u in urls if u]
        results = []
        for url in urls:
            content, status = await _read_page_with_budget(url, cache, fetched_count, max_fetches)
            if status == "cached":
                results.append(f"Cached content for {url}:\n{content}")
            elif status == "fetched":
                results.append(f"Fetched content for {url}:\n{content}")
            elif status == "budget_exhausted":
                results.append(f"Fetch budget exhausted for {url}.")
            else:
                results.append(f"Error fetching {url}: {content}")
        return "\n\n".join(results)
    
    elif name == "compareSourceFreshness":
        urls = args.get("urls", [])
        if not urls or not isinstance(urls, list):
            return "Error: Missing or invalid urls argument (expected a list of at least 2 URLs)."
        
        url_content_map = {}
        for url in urls:
            content, status = await _read_page_with_budget(url, cache, fetched_count, max_fetches)
            url_content_map[url] = content if status in ("cached", "fetched") else None
        
        from app.core.tools import build_freshness_comparison_report
        return build_freshness_comparison_report(url_content_map)
    
    else:
        # Generic tool execution
        if name in AGENT_TOOLS:
            func = AGENT_TOOLS[name]["func"]
            return await func(args)
        return f"Error: Tool {name} not found."

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
        disabled_tools = set()
        available_tools = {k: v for k, v in AGENT_TOOLS.items() if k in tools_names and k not in disabled_tools}
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
        
        # Track consecutive tool failures to provide guided retries
        tool_failures: Dict[str, int] = {}
        
        # Add the submit tool
        litellm_tools.append({
            "type": "function",
            "function": {
                "name": submit_tool_name,
                "description": "Submit the final verified findings.",
                "parameters": {"type": "object", "properties": {}}
            }
        })
        
        fetched_count = [0]
        
        for turn in range(max_turns):
            from app.core.runtime_state import is_aborted
            if await is_aborted(run_id):
                raise RuntimeError(f"Run {run_id} was aborted by user.")

            active_tools = litellm_tools

            # Log prompts before calling model
            prompt_content = json.dumps(messages, indent=2)
            agent_logger.log(
                agent=agent_name,
                event_type=AgentEventType.PROMPT,
                content=prompt_content,
                model=model if 'model' in locals() else "unknown",
                key_id=key_id if 'key_id' in locals() else "unknown"
            )


            response, model, key_id = await router.run_model(
                task=agent_name,
                messages=list(messages),
                tools=active_tools,
                run_id=run_id,
                provider_id=provider_id
            )

            # litellm response usually has tool_calls in the message
            message = response.choices[0].message
            content = message.content
            tool_calls = getattr(message, "tool_calls", None)

            # Log agent thinking/turn
            if content:
                agent_logger.log(
                    agent=agent_name,
                    event_type=AgentEventType.THOUGHT,
                    content=content,
                    model=model,
                    key_id=key_id
                )

            elif tool_calls:
                # Log that the agent is acting even if it didn't "think" in text
                tool_names = [tc.function.name for tc in tool_calls]
                agent_logger.log(
                     agent=agent_name,
                     event_type=AgentEventType.THOUGHT,
                     content=f"Agent decided to use tools: {', '.join(tool_names)}",
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

                         args_dataset = args.get("dataset")
                         if args_dataset:
                             try:
                                 dataset = json.loads(args_dataset) if isinstance(args_dataset, str) else args_dataset
                                 claims = dataset.get("Verified_Claims", [])
                                 graph = dataset.get("Knowledge_Graph", [])
                                 
                                 pending_leads = [l for l in graph if l.get("Status") == "Pending" and int(l.get("Priority", 0)) >= 7]
                                 
                                 if len(claims) < 5 and pending_leads:
                                     messages.append({
                                         "role": "tool", "tool_call_id": tool_call.id, "name": name,
                                         "content": f"Coverage Gap Detected: You have only {len(claims)} verified claims and {len(pending_leads)} high-priority pending leads. Why are you concluding now? Please address the priority leads before submitting."
                                     })
                                     continue
                                 elif len(claims) < 3:
                                     messages.append({
                                         "role": "tool", "tool_call_id": tool_call.id, "name": name,
                                         "content": "Coverage too low: Less than 3 verified claims found. Please continue researching to ensure a minimal knowledge base."
                                     })
                                     continue
                             except Exception:
                                 pass # Fallback to submitting if dataset is malformed
                         
                         # If the tool provides a dataset, use it; otherwise, fallback to content
                         args_dataset = args.get("dataset")
                         return args_dataset or content or "Findings submitted.", messages





                    if name in available_tools:
                        # Log tool request
                        agent_logger.log(
                             agent=agent_name,
                             event_type=AgentEventType.TOOL_REQ,
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
                        if name == "executePlan":
                            plan = args.get("plan", [])
                            plan_observations = []
                            results_history = []
                            
                            for i, step in enumerate(plan):
                                tool_name = step.get("tool")
                                tool_args = step.get("args", {}).copy() if isinstance(step.get("args"), dict) else {}
                                
                                # Resolve placeholders like $result_0
                                for k, v in tool_args.items():
                                    if isinstance(v, str) and v.startswith("$result_"):
                                        try:
                                            idx = int(v.split("_")[1])
                                            if idx < len(results_history):
                                                tool_args[k] = results_history[idx]
                                        except (ValueError, IndexError):
                                            pass
                                
                                try:
                                    obs = await _execute_tool(tool_name, tool_args, cache, fetched_count, max_fetches)
                                    results_history.append(obs)
                                    plan_observations.append(f"Step {i} ({tool_name}): {obs}")
                                except Exception as e:
                                    err_obs = f"Step {i} ({tool_name}) failed: {str(e)}"
                                    results_history.append(err_obs)
                                    plan_observations.append(err_obs)
                                    
                            observation = "\n\n".join(plan_observations)
                        else:
                            try:
                                observation = await _execute_tool(name, args, cache, fetched_count, max_fetches)
                                tool_failures[name] = 0
                            except Exception as e:
                                count = tool_failures.get(name, 0) + 1
                                tool_failures[name] = count
                                
                                failure_type = _classify_failure(e)
                                if failure_type == "INFRASTRUCTURE_FAILURE":
                                    if count == 1:
                                        observation = f"SYSTEM ERROR in tool {name}: {str(e)}. This is an infrastructure failure. If it fails again, the tool will be disabled for this run."
                                    else:
                                        disabled_tools.add(name)
                                        observation = f"CRITICAL FAILURE in tool {name}: {str(e)}. Tool has been disabled for the remainder of this run due to repeated infrastructure errors."
                                else:
                                    if count < 3:
                                        observation = f"Error executing tool {name}: {str(e)}. Please analyze the error, correct your parameters, and try again. (Attempt {count}/3)"
                                    else:
                                        observation = f"Tool {name} has failed {count} times consecutively. It may be fundamentally broken or the requested operation is impossible. Please attempt a different approach or use an alternative tool."



                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": observation
                        })
                        
                        # Log tool response
                        agent_logger.log(
                             agent=agent_name,
                             event_type=AgentEventType.TOOL_RES,
                             content=f"Observation from {name}: {observation}",
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
            
            # No tool calls at all.
            if not content:
                messages.append({"role": "user", "content": "Please use the available tools to research and eventually call the submit tool."})
                continue

            
            return content, messages
            
        if attempt < max_retries:
            continue
        else:
            return "MAX_TURNS_REACHED", messages

    return "Error: Max turns reached without submission.", messages
