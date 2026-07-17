import asyncio
import json
from enum import Enum, auto
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.acquisition_cache import acquisition_cache
from app.core.agent_event_types import AgentEventType
from app.core.agent_logger import agent_logger
from app.core.context_manager import ContextManager
from app.core.importers.ocr_importer import ocr_importer
from app.core.router import router
from app.core.tools import AGENT_TOOLS
from app.db.notebook_schema import AcquisitionArtifact

context_manager = ContextManager()


class Capability(Enum):
    READ_MAIN_DB = auto()
    WRITE_MAIN_DB = auto()
    READ_WORKSPACE = auto()
    WRITE_WORKSPACE = auto()
    ACQUISITION = auto()
    SUBMIT = auto()


# Tool to Capability mapping
TOOL_CAPABILITIES = {
    "queryArtifacts": Capability.READ_MAIN_DB,
    "upsertArtifacts": Capability.WRITE_MAIN_DB,
    "updateArtifact": Capability.WRITE_MAIN_DB,
    "loadNotebookEntry": Capability.READ_WORKSPACE,
    "saveNotebookEntry": Capability.WRITE_WORKSPACE,
    "deleteNotebookEntry": Capability.WRITE_WORKSPACE,
    "webSearch": Capability.ACQUISITION,
    "fetchPage": Capability.ACQUISITION,
    "ocrImage": Capability.ACQUISITION,
    "compareSourceFreshness": Capability.ACQUISITION,
}


async def _read_page_cached(url: str) -> tuple[str, str]:
    """Read page content through AcquisitionCache (persistent, content-hash keyed, shared globally).
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

        return (
            doc.extracted_text or str(doc.metadata.get("error", "No content")),
            "fetched",
        )
    except (ValueError, TypeError, KeyError, AttributeError) as e:
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
    _run_id: str | None = None,
    _agent_name: str | None = None,
    _model: str | None = None,
    _key_id: str | None = None,
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
            content, status = await _read_page_cached(url)
            if status in ("fetched", "cached"):
                results.append(f"Fetched content for {url}:\n{content}")
            else:
                results.append(f"Error fetching {url}: {content}")
        return "\n\n".join(results)

    if name == "compareSourceFreshness":
        urls = args.get("urls", [])
        if not urls or not isinstance(urls, list):
            return "Error: Missing or invalid urls argument (expected a list of at least 2 URLs)."

        url_content_map = {}
        for url in urls:
            content, status = await _read_page_cached(url)
            url_content_map[url] = content if status in ("fetched", "cached") else None

        from app.core.tools import build_freshness_comparison_report
        return build_freshness_comparison_report(url_content_map)

    if name == "ocrImage":
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
        except (ValueError, TypeError, AttributeError) as e:
            return f"OCR failed: {e!s}"

    if name in AGENT_TOOLS:
        print(f"DEBUG: _execute_tool calling {name} from AGENT_TOOLS")
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
    history: list[dict[str, Any]] | None = None,
    required_capabilities: set[Capability] | None = None,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Runs a tool-using agent loop.
    Uses global AcquisitionCache (persistent, content-hash keyed, shared across runs).
    Returns (success, final_answer, full_messages_history).
    """
    from app.core.runtime_state import (
        get_current_summary,
        set_current_run_id,
        set_current_summary,
    )
    from app.services.settings_service import SettingsService

    set_current_run_id(run_id)

    # Reconfigure context manager from settings
    settings_service = SettingsService()
    settings = settings_service.get_all_settings().get("general_settings", {})
    max_tokens = int(settings.get("MAX_TOKENS", 32000))
    summary_threshold = float(settings.get("COMPRESSION_THRESHOLD", 0.8))
    context_manager.reconfigure(max_tokens, summary_threshold)

    # If we are resuming, check if there's an existing summary
    last_summary = get_current_summary()
    if last_summary:
        # If we have a summary, we might want to ensure it's in the history if not already
        # But for simplicity, we'll let the compression logic handle it or
        # we can inject it into the system prompt if it's a new run.
        pass

    # Append context pruning notice to system prompt
    system_prompt += (
        "\n\n[CONTEXT MANAGEMENT NOTICE]: Raw observations from fetchPage, webSearch, and ocrImage "
        "are automatically pruned from your history once you use a writing tool (upsertArtifacts, "
        "updateArtifact, or saveNotebookEntry). Ensure you have extracted all necessary information "
        "from your sources before committing it to the database."
    )


    for attempt in range(max_retries + 1):
        model = None # Track current model for token counting
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

        # If we are resuming, check if there's an existing summary
        last_summary = get_current_summary()
        if last_summary:
            summary_found = False
            for m in messages:
                if m.get("role") == "system" and last_summary in m.get("content", ""):
                    summary_found = True
                    break
            if not summary_found:
                if messages and messages[0]["role"] == "system":
                    messages.insert(1, {"role": "system", "content": f"Context Summary of previous turns:\n{last_summary}"})
                else:
                    messages.insert(0, {"role": "system", "content": f"Context Summary of previous turns:\n{last_summary}"})


        # Filter tools and prepare litellm-compatible tool definitions
        disabled_tools = set()
        filtered_tools_names = tools_names
        if required_capabilities is not None:
            filtered_tools_names = [
                name for name in tools_names
                if name not in TOOL_CAPABILITIES or TOOL_CAPABILITIES[name] in required_capabilities
            ]

        available_tools = {
            k: v
            for k, v in AGENT_TOOLS.items()
            if k in filtered_tools_names and k not in disabled_tools
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

            # Context Management: Compress history if token budget is exceeded
            if model:
                current_tokens = context_manager.count_tokens(messages, model)
                if current_tokens > context_manager.max_tokens * context_manager.summary_threshold:
                    messages, summary = await context_manager.compress_context(
                        messages=messages,
                        model=model,
                        router_instance=router,
                        system_prompt=system_prompt,
                        user_goal=user_prompt
                    )
                    if summary:
                        set_current_summary(summary)


            # Enforce minimum turns before allowing submission
            if _turn < min_turns:
                pass

            active_tools = litellm_tools

            # Log prompts before calling model
            prompt_content = json.dumps(messages)

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

            if content:
                agent_logger.log(
                    agent=agent_name,
                    event_type=AgentEventType.THOUGHT,
                    content=content,
                    model=model,
                    key_id=key_id,
                )
            elif tool_calls:
                tool_names = [tc.function.name for tc in tool_calls]
                agent_logger.log(
                    agent=agent_name,
                    event_type=AgentEventType.THOUGHT,
                    content=f"Agent decided to use tools: {', '.join(tool_names)}",
                    model=model,
                    key_id=key_id,
                )

            if tool_calls:
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
                                dataset = json.loads(args_dataset) if isinstance(args_dataset, str) else args_dataset
                                claims = dataset.get("Verified_Claims", [])
                                graph = dataset.get("Knowledge_Graph", [])
                                pending_leads = [lead for lead in graph if lead.get("Status") == "Pending" and int(lead.get("Priority", 0)) >= 7]
                                if len(claims) < 5 and pending_leads:
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": name,
                                        "content": f"Coverage Gap Detected: You have only {len(claims)} verified claims and {len(pending_leads)} high-priority pending leads. Why are you concluding now? Please address the priority leads before submitting.",
                                    })
                                    continue
                                if len(claims) < 3:
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": name,
                                        "content": "Coverage too low: Less than 3 verified claims found. Please continue researching to ensure a minimal knowledge base.",
                                    })
                                    continue
                            except json.JSONDecodeError:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": name,
                                    "content": "Submission rejected: The dataset provided is not valid JSON. Please ensure you return a properly formatted JSON object.",
                                })
                                return True, "Submission rejected: The dataset provided is not valid JSON. Please ensure you return a properly formatted JSON object.", messages
                            except (ValueError, TypeError, KeyError) as e:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": name,
                                    "content": f"Submission rejected: Error parsing dataset: {e!s}. Please check your formatting.",
                                })
                                continue

                        return True, args_dataset or content or "Findings submitted.", messages

                    if name in available_tools:
                        agent_logger.log(
                            agent=agent_name,
                            event_type=AgentEventType.TOOL_REQ,
                            content=f"Calling {name} with args {json.dumps(args)}",
                            model=model,
                            key_id=key_id,
                        )

                        if name == "executePlan":
                            plan = args.get("plan", [])
                            plan_observations = [None] * len(plan)
                            results_history = [None] * len(plan)
                            completed_steps = set()

                            while len(completed_steps) < len(plan):
                                ready_steps = []
                                for i, step in enumerate(plan):
                                    if i in completed_steps:
                                        continue
                                    tool_args = step.get("args", {}).copy() if isinstance(step.get("args"), dict) else {}
                                    can_run = True
                                    for v in tool_args.values():
                                        if isinstance(v, str) and v.startswith("$result_"):
                                            try:
                                                idx = int(v.split("_")[1])
                                                if idx >= len(plan) or (idx >= 0 and results_history[idx] is None):
                                                    can_run = False
                                                    break
                                            except (ValueError, IndexError):
                                                pass
                                    if can_run:
                                        ready_steps.append(i)

                                if not ready_steps:
                                    break

                                tasks = []
                                for i in ready_steps:
                                    step = plan[i]
                                    tool_name = step.get("tool")
                                    tool_args = step.get("args", {}).copy() if isinstance(step.get("args"), dict) else {}
                                    for k, v in tool_args.items():
                                        if isinstance(v, str) and v.startswith("$result_"):
                                            try:
                                                idx = int(v.split("_")[1])
                                                if 0 <= idx < len(results_history):
                                                    tool_args[k] = results_history[idx]
                                            except (ValueError, IndexError):
                                                pass
                                    if agent_name:
                                        agent_logger.log(
                                            agent=agent_name,
                                            event_type=AgentEventType.STEP,
                                            content=f"Executing step {i+1}/{len(plan)} (Concurrent): {tool_name} with {tool_args}",
                                            model=model or "unknown",
                                            key_id=key_id or "unknown",
                                        )
                                    tasks.append(_execute_tool(tool_name, tool_args, run_id, agent_name=agent_name, model=model, key_id=key_id))

                                results = await asyncio.gather(*tasks, return_exceptions=True)
                                for i, res in zip(ready_steps, results):
                                    if isinstance(res, Exception):
                                        obs = f"Step {i} failed: {res!s}"
                                    else:
                                        obs = res
                                    results_history[i] = obs
                                    plan_observations[i] = f"Step {i} ({plan[i].get('tool')}): {obs}"
                                    completed_steps.add(i)

                                observation = "\\n\\n".join([o for o in plan_observations if o is not None])
                                agent_logger.log(
                                    agent=agent_name,
                                    event_type=AgentEventType.TOOL_RES,
                                    content=f"Observation from executePlan: {observation}",
                                    model=model,
                                    key_id=key_id,
                                )
                            else:
                                try:
                                    observation = await _execute_tool(name, args, run_id, agent_name=agent_name, model=model, key_id=key_id)
                                    tool_failures[name] = 0
                                except (ValueError, TypeError, KeyError, RuntimeError, AttributeError, OSError) as e:
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


                    # Prune raw observations if a writing tool was used
                    messages = context_manager.prune_raw_observations(messages, name)

                    # If it's a notebook writing tool, also trigger compression
                    if name == "saveNotebookEntry" and model:
                        current_tokens = context_manager.count_tokens(messages, model)
                        if current_tokens > context_manager.max_tokens * context_manager.summary_threshold:
                            messages, summary = await context_manager.compress_context(
                                messages=messages,
                                model=model,
                                router_instance=router,
                                system_prompt=system_prompt,
                                user_goal=user_prompt
                            )
                            if summary:
                                set_current_summary(summary)
                    continue

                if not content:
                    messages.append(
                        {
                            "role": "user",
                            "content": "Please use the available tools to research and eventually call the submit tool.",
                        }
                    )
                    continue

                return (True, content, messages)

        if attempt < max_retries:
            continue

        return (False, "MAX_TURNS_REACHED", messages)

    return (False, "Error: Max turns reached without submission.", messages)
