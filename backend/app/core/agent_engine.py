import json
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.acquisition_cache import acquisition_cache
from app.core.agent_event_types import AgentEventType
from app.core.agent_logger import agent_logger
from app.core.router import router
from app.core.tools import AGENT_TOOLS
from app.db.unconfirmed_schema import AcquisitionArtifact
from app.core.importers.ocr_importer import ocr_importer


async def _read_page_cached(url: str, run_id: str | None = None):
    """
    Read page content through AcquisitionCache (persistent, content-hash keyed, shared globally).
    Returns (content_or_error_message, status).
    """
    from app.core.importers.web_page_importer import WebPageImporter

    cached = acquisition_cache.get_from_lru(url)
    if cached:
        return cached.extracted_text, "cached"

    persistent = acquisition_cache.repo.get_by_url(url, limit=1)
    if persistent:
        acquisition_cache._set_lru(url, persistent[0])
        return persistent[0].extracted_text, "cached"

    try:
        importer = WebPageImporter()
        doc = await importer.fetch(url)

        if doc.extracted_text:
            existing = acquisition_cache.repo.get_by_hash(doc.content_hash)
            if not existing:
                artifact = AcquisitionArtifact(
                    content_hash=doc.content_hash,
                    source_url=url,
                    content_type="web_page",
                    extracted_text=doc.extracted_text,
                    engine_name="trafilatura",
                )
                stored = acquisition_cache.repo.store(artifact)
                acquisition_cache._set_lru(url, stored)

        return doc.extracted_text or str(doc.metadata.get("error", "No content")), "fetched"
    except Exception as e:
        return str(e), "error"


def _classify_failure(e: Exception) -> str:
    """Classify failure as RECOVERABLE or INFRASTRUCTURE_FAILURE."""
    if isinstance(e, (ProgrammingError, OperationalError)):
        return "INFRASTRUCTURE_FAILURE"

    err_msg = str(e).lower()
    infra_keywords = [
        "no such column",
        "no such table",
        "missing column",
        "undefined column",
        "column does not exist",
    ]
    if any(kw in err_msg for kw in infra_keywords):
        return "INFRASTRUCTURE_FAILURE"

    return "RECOVERABLE"


async def _execute_tool(
    name: str,
    args: dict[str, Any],
    run_id: str | None = None,
) -> str:
    """Execute a tool, routing fetchPage/compareSourceFreshness through shared cache."""
    if name == "fetchPage":
        urls = (
            args.get("urls", [])
            if isinstance(args.get("urls"), list)
            else [args.get("url")]
        )
        urls = [u for u in urls if u]
        results = []
        for url in urls:
            content, status = await _read_page_cached(url, run_id)
            if status in ("fetched", "cached"):
                results.append(f"Fetched content for {url}:\n{content}")
            else:
                results.append(f"Error fetching {url}: {content}")
        return "\n\n".join(results)

    elif name == "compareSourceFreshness":
        urls = args.get("urls", [])
        if not urls or not isinstance(urls, list):
            return "Error: Missing or invalid urls argument (expected a list of at least 2 URLs)."

        url_content_map = {}
        for url in urls:
            content, status = await _read_page_cached(url, run_id)
            url_content_map[url] = content if status in ("fetched", "cached") else None

        from app.core.tools import build_freshness_comparison_report

        return build_freshness_comparison_report(url_content_map)

    elif name == "ocrImage":
        image_url = args.get("image_url")
        image_data = args.get("image_data")
        preferred = args.get("preferred_engine")
        use_gpu = args.get("use_gpu")

        if not image_url and not image_data:
            return "Error: Provide either image_url or image_data."

        try:
            doc = await ocr_importer.fetch(
                image_url or "data:image/unknown;base64,",
                image_data=image_data,
                preferred_engine=preferred,
                use_gpu=use_gpu,
            )
            if doc.extracted_text:
                gpu_info = ""
                meta = doc.metadata or {}
                if meta.get("gpu"):
                    gpu_info = " [GPU]"
                parts = [f"OCR result ({doc.engine_name}{gpu_info}):", doc.extracted_text]
                if doc.structured_data:
                    parts.append(f"Structured data: {doc.structured_data}")
                return "\n\n".join(parts)
            return f"OCR returned no text. Status: {doc.content_type}. Engine: {doc.engine_name or 'none'}."
        except Exception as e:
            return f"OCR failed: {e!s}"

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
    tools_names: list[str],
    submit_tool_name: str,
    max_turns: int = 50,
    min_turns: int = 0,
    max_retries: int = 1,
    provider_id: int | None = None,
    history: list[dict[str, str]] | None = None,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Runs a tool-using agent loop.
    Uses global AcquisitionCache (persistent, content-hash keyed, shared across runs).
    Returns (success, final_answer, full_messages_history).
    """
    from app.core.runtime_state import set_current_run_id
    set_current_run_id(run_id)

    for attempt in range(max_retries + 1):
        if history:
            messages = list(history)
            # Ensure system prompt is current if it's the first message or needs update
            if not messages or messages[0]["role"] != "system":
                messages.insert(0, {"role": "system", "content": system_prompt})
            elif messages[0]["role"] == "system":
                messages[0]["content"] = system_prompt

            # If the history doesn't end with the current user prompt, add it
            if (
                not messages
                or messages[-1]["role"] != "user"
                or messages[-1]["content"] != user_prompt
            ):
                messages.append({"role": "user", "content": user_prompt})
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        # Filter tools and prepare litellm-compatible tool definitions
        disabled_tools = set()
        available_tools = {
            k: v
            for k, v in AGENT_TOOLS.items()
            if k in tools_names and k not in disabled_tools
        }
        litellm_tools = []
        for name, info in available_tools.items():
            litellm_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": info["description"],
                        "parameters": info["parameters"],
                    },
                }
            )

        # Track consecutive tool failures to provide guided retries
        tool_failures: dict[str, int] = {}

        # Add the submit tool
        litellm_tools.append(
            {
                "type": "function",
                "function": {
                    "name": submit_tool_name,
                    "description": "Submit the final verified findings.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )

        for _turn in range(max_turns):
            from app.core.runtime_state import is_aborted

            if await is_aborted(run_id):
                raise RuntimeError(f"Run {run_id} was aborted by user.")

            # Enforce minimum turns before allowing submission
            if _turn < min_turns:
                # We don't stop the agent, but we will block the submit tool if it tries to call it.
                pass

            active_tools = litellm_tools

            # Log prompts before calling model
            prompt_content = json.dumps(messages, indent=2)

            response, model, key_id = await router.run_model(
                task=agent_name,
                messages=list(messages),
                tools=active_tools,
                run_id=run_id,
                provider_id=provider_id,
            )

            agent_logger.log(
                agent=agent_name,
                event_type=AgentEventType.PROMPT,
                content=prompt_content,
                model=model,
                key_id=key_id,
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
                    key_id=key_id,
                )

            elif tool_calls:
                # Log that the agent is acting even if it didn't "think" in text
                tool_names = [tc.function.name for tc in tool_calls]
                agent_logger.log(
                    agent=agent_name,
                    event_type=AgentEventType.THOUGHT,
                    content=f"Agent decided to use tools: {', '.join(tool_names)}",
                    model=model,
                    key_id=key_id,
                )

            if tool_calls:
                # Append assistant message with tool calls to history
                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )
                for tool_call in tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if name == submit_tool_name:
                        # 1. Enforce minimum turns
                        if _turn < min_turns:
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": name,
                                    "content": f"Submission rejected: Minimum research turns ({min_turns}) not yet reached. Current turn: {_turn + 1}. Please continue exploring and verifying claims before submitting.",
                                }
                            )
                            continue

                        args_dataset = args.get("dataset")
                        if args_dataset:
                            try:
                                dataset = (
                                    json.loads(args_dataset)
                                    if isinstance(args_dataset, str)
                                    else args_dataset
                                )
                                claims = dataset.get("Verified_Claims", [])
                                graph = dataset.get("Knowledge_Graph", [])

                                pending_leads = [
                                    lead
                                    for lead in graph
                                    if lead.get("Status") == "Pending"
                                    and int(lead.get("Priority", 0)) >= 7
                                ]

                                if len(claims) < 5 and pending_leads:
                                    messages.append(
                                        {
                                            "role": "tool",
                                            "tool_call_id": tool_call.id,
                                            "name": name,
                                            "content": f"Coverage Gap Detected: You have only {len(claims)} verified claims and {len(pending_leads)} high-priority pending leads. Why are you concluding now? Please address the priority leads before submitting.",
                                        }
                                    )
                                    continue
                                elif len(claims) < 3:
                                    messages.append(
                                        {
                                            "role": "tool",
                                            "tool_call_id": tool_call.id,
                                            "name": name,
                                            "content": "Coverage too low: Less than 3 verified claims found. Please continue researching to ensure a minimal knowledge base.",
                                        }
                                    )
                                    continue
                            except json.JSONDecodeError:
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": name,
                                        "content": "Submission rejected: The dataset provided is not valid JSON. Please ensure you return a properly formatted JSON object.",
                                    }
                                )
                                return True, "Submission rejected: The dataset provided is not valid JSON. Please ensure you return a properly formatted JSON object.", messages
                            except Exception as e:






                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": name,
                                        "content": f"Submission rejected: Error parsing dataset: {e!s}. Please check your formatting.",
                                    }
                                )
                                continue

                        # If the tool provides a dataset, use it; otherwise, fallback to content
                        return (
                            True,
                            args_dataset or content or "Findings submitted.",
                            messages,
                        )

                    if name in available_tools:
                        # Log tool request
                        agent_logger.log(
                            agent=agent_name,
                            event_type=AgentEventType.TOOL_REQ,
                            content=f"Calling {name} with args {json.dumps(args)}",
                            model=model,
                            key_id=key_id,
                        )

                        if name == "executePlan":
                            plan = args.get("plan", [])
                            plan_observations = []
                            results_history = []

                            for i, step in enumerate(plan):
                                tool_name = step.get("tool")
                                tool_args = (
                                    step.get("args", {}).copy()
                                    if isinstance(step.get("args"), dict)
                                    else {}
                                )

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
                                    obs = await _execute_tool(
                                        tool_name,
                                        tool_args,
                                        run_id,
                                    )
                                    results_history.append(obs)
                                    plan_observations.append(
                                        f"Step {i} ({tool_name}): {obs}"
                                    )
                                except Exception as e:
                                    err_obs = f"Step {i} ({tool_name}) failed: {e!s}"
                                    results_history.append(err_obs)
                                    plan_observations.append(err_obs)

                            observation = "\n\n".join(plan_observations)
                        else:
                            try:
                                observation = await _execute_tool(
                                    name, args, run_id
                                )
                                tool_failures[name] = 0
                            except Exception as e:
                                count = tool_failures.get(name, 0) + 1
                                tool_failures[name] = count

                                failure_type = _classify_failure(e)
                                if failure_type == "INFRASTRUCTURE_FAILURE":
                                    if count == 1:
                                        observation = f"SYSTEM ERROR in tool {name}: {e!s}. This is an infrastructure failure. If it fails again, the tool will be disabled for this run."
                                    else:
                                        disabled_tools.add(name)
                                        observation = f"CRITICAL FAILURE in tool {name}: {e!s}. Tool has been disabled for the remainder of this run due to repeated infrastructure errors."
                                else:
                                    if count < 3:
                                        observation = f"Error executing tool {name}: {e!s}. Please analyze the error, correct your parameters, and try again. (Attempt {count}/3)"
                                    else:
                                        observation = f"Tool {name} has failed {count} times consecutively. It may be fundamentally broken or the requested operation is impossible. Please attempt a different approach or use an alternative tool."

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": name,
                                "content": observation,
                            }
                        )

                        # Log tool response
                        agent_logger.log(
                            agent=agent_name,
                            event_type=AgentEventType.TOOL_RES,
                            content=f"Observation from {name}: {observation}",
                            model=model,
                            key_id=key_id,
                        )

                    else:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": name,
                                "content": f"Error: Tool {name} not found.",
                            }
                        )

                # After executing tool calls, the agent needs to process observations
                continue

            # No tool calls at all.
            if not content:
                messages.append(
                    {
                        "role": "user",
                        "content": "Please use the available tools to research and eventually call the submit tool.",
                    }
                )
                continue

            return (
                True,
                content,
                messages
            )

        if attempt < max_retries:
            continue
        else:
            return (
                False,
                "MAX_TURNS_REACHED",
                messages
            )

    return (
        False,
        "Error: Max turns reached without submission.",
        messages
    )
