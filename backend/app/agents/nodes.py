import asyncio
from typing import Any

from app.agents.workflow_state import OmniverseState
from app.core.agent_engine import run_agent
from app.core.context import set_current_universe
from app.research.researcher import research_single_world
from app.research.summarizer import summarize_universe
from app.services.execution_service import ExecutionService
from app.services.settings_service import SettingsService
from app.workflow.extrapolation_workflow import extrapolation_node as extrapolation_impl
from app.workflow.tiering_workflow import architecture_node as architecture_impl


async def research_node(state: OmniverseState) -> dict[str, Any]:
    run_id = state.get("run_id")
    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")

    target_worlds = state.get("target_worlds", [])
    focused_features = state.get("focused_features")

    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id,
        "Manager",
        f"Starting parallel research phase for {len(target_worlds)} worlds",
        "RESEARCHING",
        state,
    )

    successful_results = []
    errors = []
    verified_worlds = []

    settings_service = SettingsService()
    setting = settings_service.get_setting("MAX_PARALLEL_AGENTS")
    batch_size = int(setting.value) if setting and setting.value else 5
    if batch_size <= 0:
        batch_size = 1

    focus_str = ", ".join(focused_features) if focused_features else None

    for i in range(0, len(target_worlds), batch_size):
        batch = target_worlds[i : i + batch_size]
        tasks = [
            research_single_world(world, run_id, focus=focus_str)
            for world in batch
        ]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in batch_results:
            if isinstance(r, Exception):
                errors.append(str(r))
            elif isinstance(r, dict):
                successful_results.append(r)
                verified_worlds.append(r["name"])

    exec_service.log_transition(
        run_id, "Manager", "Completed parallel research phase", "COMPLETED", state
    )

    if not verified_worlds:
        exec_service.log_transition(
            run_id,
            "Manager",
            f"All {len(target_worlds)} world(s) failed research; nothing to consolidate. Errors: {errors}",
            "FAILED",
            state,
        )
        return {
            "research_results": successful_results,
            "verified_worlds": verified_worlds,
            "errors": errors,
            "active_task": "FINISHED",
        }

    next_task = "DB_INTEGRATION"
    return {
        "research_results": successful_results,
        "verified_worlds": verified_worlds,
        "errors": errors,
        "active_task": next_task,
    }


async def db_integrator_node(state: OmniverseState) -> dict[str, Any]:
    run_id = state.get("run_id")
    research_results = state.get("research_results", [])

    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id,
        "DB Integrator",
        f"Integrating data for {len(research_results)} worlds",
        "INTEGRATING",
        state,
    )

    for result in research_results:
        world_name = result["name"]
        verified_data = result["summary"]
        status = result.get("status", "VERIFIED")

        from app.agents.prompts import get_cleanup_prompt, get_db_agent_prompt

        prompt = get_db_agent_prompt()
        user_prompt_data = f"Universe: {world_name}\nVerification Status: {status}\n\nVerified Research Data:\n{verified_data}"

        set_current_universe(world_name)

        success, final_ans, history = await run_agent(
            agent_name="DB Architect",
            system_prompt=prompt["system"],
            user_prompt=user_prompt_data,
            step=f"Integrate {world_name}",
            run_id=run_id,
            tools_names=["queryClaims", "upsertClaims"],
            submit_tool_name="submit_integration",
        )
        
        # Only proceed to cleanup if integration was successful
        if success:
            cleanup_prompt = get_cleanup_prompt()
            # Truncate history to only include the last 5 messages to avoid context bloat
            truncated_history = history[-5:] if history else []
            await run_agent(
                agent_name="DB Architect",
                system_prompt=cleanup_prompt["system"],
                user_prompt=f"Clean up unconfirmed staging for {world_name}",
                step=f"Cleanup {world_name}",
                run_id=run_id,
                tools_names=[
                    "queryClaims",
                    "queryUnconfirmedClaims",
                    "deleteUnconfirmedClaim",
                ],
                submit_tool_name="submit_cleanup",
                history=truncated_history,
            )
        else:
            exec_service.log_transition(
                run_id,
                "DB Integrator",
                f"Integration failed for {world_name} ({final_ans}). Skipping cleanup to preserve staging data.",
                "FAILED",
                state,
            )

    # Mark all integrated universes as explored in one batch
    from app.services.universe_service import UniverseService

    uni_service = UniverseService()
    universes = uni_service.get_by_names([r["name"] for r in research_results])
    for u in universes:
        u.is_explored = True
    uni_service.update_batch(universes)

    exec_service.log_transition(
        run_id,
        "DB Integrator",
        "All research integrated and staging cleaned.",
        "COMPLETED",
        state,
    )
    return {"active_task": "SUMMARY"}


async def summary_node(state: OmniverseState) -> dict[str, Any]:
    run_id = state.get("run_id")
    verified_worlds = state.get("verified_worlds", [])

    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id,
        "Summarizer",
        f"Creating polished summaries for {len(verified_worlds)} worlds",
        "SUMMARIZING",
        state,
    )

    from app.services.universe_service import UniverseService

    uni_service = UniverseService()
    universes = uni_service.get_by_names(verified_worlds)
    universe_ids = [u.id for u in universes]

    tasks = [summarize_universe(uid, run_id) for uid in universe_ids]
    await asyncio.gather(*tasks)

    exec_service.log_transition(
        run_id,
        "Summarizer",
        "All summaries generated successfully.",
        "COMPLETED",
        state,
    )

    if state.get("is_focused_search"):
        return {"active_task": "ARCHITECTURE"}

    return {"active_task": "DB_INTEGRATION"}


async def manager_node(state: OmniverseState) -> dict[str, Any]:
    run_id = state.get("run_id")
    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id, "Manager", "Routing pipeline state", "COMPLETED", state
    )
    return {"active_task": state.get("active_task", "RESEARCH")}


async def architecture_node(state: OmniverseState) -> dict[str, Any]:
    return await architecture_impl(state)


async def extrapolation_node(state: OmniverseState) -> dict[str, Any]:
    return await extrapolation_impl(state)
