from typing import Dict, Any
from app.core.agent_engine import run_agent
from app.agents.prompts import get_synthesis_prompt
from app.services.execution_service import ExecutionService
from app.services.settings_service import SettingsService
from app.services.universe_service import UniverseService

async def consolidation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state.get("run_id")
    from app.core.runtime_state import is_aborted
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
    
    exec_service = ExecutionService()
    settings_service = SettingsService()
    uni_service = UniverseService()
    
    exec_service.log_transition(run_id, "Consolidator", "Starting synthesis of target worlds", "IN_PROGRESS", state)
    
    verified_world_names = state.get("verified_worlds", [])
    universes = uni_service.repo.get_by_names(verified_world_names)
    reports = [f"World: {u.name}\nSummary: {u.summary}\nStructured Data: {u.raw_data}" for u in universes]
    
    synthesis_prompts = get_synthesis_prompt(reports)
    
    consolidated_dataset, _ = await run_agent(
        agent_name="Consolidator",
        system_prompt=synthesis_prompts["system"],
        user_prompt=synthesis_prompts["user"],
        step="Synthesis",
        run_id=run_id,
        tools_names=[],
        submit_tool_name="submit_synthesis"
    )
    
    exec_service.log_transition(run_id, "Consolidator", "Completed synthesis of world datasets", "COMPLETED", state)
    
    settings_service.update_general_setting("CONSOLIDATED_DATASET", consolidated_dataset)
        
    return {
        "active_task": "ARCHITECTURE"
    }
