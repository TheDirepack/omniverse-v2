import json
import asyncio
from typing import List, Dict, Any, Optional
from app.core.agent_engine import run_agent, FetchCache
from app.core.context import set_current_universe
from app.core.retry_handler import RetryHandler
from app.core.validators import validate_research_json
from app.agents.prompts import (
    get_researcher_prompt,
    get_critic_prompt
)
from app.services.execution_service import ExecutionService

def audit_success(audit_result: str) -> bool:
    try:
        parsed = json.loads(audit_result)
        status = str(parsed.get("Verification_Status", "")).strip().upper()
        if status:
            return status == "SUCCESS"
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    upper = audit_result.upper()
    if "REVISION_REQUIRED" in upper:
        return False
    
    lines = upper.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("SUCCESS") or line.startswith("VERIFIED") or line.startswith("STATUS: SUCCESS") or line.startswith("STATUS: VERIFIED"):
            return True
            
    return False

async def save_audit_artifacts(world_name: str, retry_handler: RetryHandler, final_result: str):
    from app.core.tools import tool_save_unconfirmed_trait
    
    # Save audit history
    await tool_save_unconfirmed_trait({
        "name": "Audit History",
        "value": json.dumps(retry_handler.feedback_history, indent=2),
        "category": "Audit",
        "confidence": "high"
    })
    
    # Save final knowledge graph
    await tool_save_unconfirmed_trait({
        "name": "Final Knowledge Graph",
        "value": final_result,
        "category": "Research",
        "confidence": "high"
    })

async def research_single_world(world_name: str, run_id: str, focus: str | None = None, fetch_cache: FetchCache | None = None) -> Dict[str, Any]:

    from app.core.runtime_state import is_aborted
    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")
    
    from app.services.universe_service import UniverseService
    from app.services.tiering_service import TieringService
    from app.services.settings_service import SettingsService
    
    uni_service = UniverseService()
    tier_service = TieringService()
    settings_service = SettingsService()
    
    universe = uni_service.get_universe(world_name)
    if universe:
        tier_service.clear_world_tier(universe.id)
    
    stage_label = f"{world_name} focused on {focus}" if focus else world_name
    set_current_universe(world_name)
    
    exec_service = ExecutionService()
    exec_service.log_transition(run_id, "Research Unit", f"Initiating incremental research for world: {stage_label}", "IN_PROGRESS", {})

    researcher_tools = ["webSearch", "fetchPage", "compareSourceFreshness", "queryClaims", "queryUnconfirmedClaims", "saveUnconfirmedClaim"]
    auditor_tools = ["fetchPage", "compareSourceFreshness", "queryClaims", "queryUnconfirmedClaims"]

    retry_handler = RetryHandler(max_iterations=3)

    try:
        while retry_handler.current_iteration < retry_handler.max_iterations:
            i = retry_handler.iteration_count
            research_queue = retry_handler.get_research_queue()
            feedback_summary = retry_handler.get_feedback_summary()

            researcher_prompt = get_researcher_prompt(
                entity=world_name,
                requirements="Collect comprehensive canonical wiki data.",
                focus=focus,
                previous_dataset=retry_handler.last_result,
                outstanding_corrections=feedback_summary
            )
            
            user_prompt = researcher_prompt["user"]
            if research_queue and feedback_summary == "None":
                user_prompt += f"\n\n{research_queue}\n\nPrioritize these leads in your tool use."
            elif research_queue:
                user_prompt += f"\n\nSECONDARY LEADS (Address only after all corrections are resolved):\n{research_queue}"

            min_turns_setting = settings_service.get_setting("MIN_RESEARCH_TURNS")
            min_turns = int(min_turns_setting.value) if min_turns_setting and min_turns_setting.value else 6
            
            result, turn_history = await run_agent(
                agent_name="Researcher",
                system_prompt=researcher_prompt["system"],
                user_prompt=user_prompt,
                step=f"Research (Attempt {i})",
                run_id=run_id,
                tools_names=researcher_tools,
                submit_tool_name="submit_research",
                min_turns=min_turns,
                fetch_cache=fetch_cache,
                history=retry_handler.agent_history
            )



            
            # Deterministic Validation
            try:
                parsed_result = json.loads(result)
                is_valid, val_errors = validate_research_json(parsed_result)
                if not is_valid:
                    # Inject deterministic errors into the flow
                    # We'll let the auditor see them or handle them as a failure
                    deterministic_critique = json.dumps({
                        "Verification_Status": "Revision_Required",
                        "Correction_Queue": [
                            {"Error_Type": "Schema", "Issue": err, "Required_Fix": "Fix JSON schema violation"} 
                            for err in val_errors
                        ]
                    })
                    # If deterministic validation fails, we treat it as a failed audit 
                    # and skip the LLM auditor to save tokens/time, OR we use it to augment.
                    # Let's use it to augment the auditor's critique if we still want the auditor's depth check.
                    # But for simplicity and "Logic & Reliability", we can prioritize deterministic failures.
                    if val_errors:
                        retry_handler.update_state(result, deterministic_critique, turn_history)
                        if retry_handler.is_final_attempt():
                            sifted = retry_handler.handle_final_attempt(deterministic_critique)
                            if sifted:
                                await save_audit_artifacts(world_name, retry_handler, sifted)
                                return {"name": world_name, "summary": sifted, "status": "PARTIAL"}
                        continue 
            except json.JSONDecodeError:
                deterministic_critique = json.dumps({
                    "Verification_Status": "Revision_Required",
                    "Correction_Queue": [{"Error_Type": "Schema", "Issue": "Invalid JSON", "Required_Fix": "Return a parseable JSON object"}]
                })
                retry_handler.update_state(result, deterministic_critique, turn_history)
                if retry_handler.is_final_attempt():
                    sifted = retry_handler.handle_final_attempt(deterministic_critique)
                    if sifted:
                        await save_audit_artifacts(world_name, retry_handler, sifted)
                        return {"name": world_name, "summary": sifted, "status": "PARTIAL"}
                continue

            critic_prompt = get_critic_prompt(
                data=result, 
                criteria=researcher_prompt["system"], 
                previous_corrections=feedback_summary,
                is_final_attempt=retry_handler.is_final_attempt()
            )
            
            critique, _ = await run_agent(
                agent_name="Logic Auditor",
                system_prompt=critic_prompt["system"],
                user_prompt=critic_prompt["user"],
                step=f"Audit (Attempt {i})",
                run_id=run_id,
                tools_names=auditor_tools,
                submit_tool_name="submit_audit",
                fetch_cache=fetch_cache
            )
            
            if audit_success(critique):
                await save_audit_artifacts(world_name, retry_handler, result)
                return {"name": world_name, "summary": result, "status": "VERIFIED"}
            
            retry_handler.update_state(result, critique, turn_history)
            
            if retry_handler.is_final_attempt():
                sifted = retry_handler.handle_final_attempt(critique)
                if sifted:
                    await save_audit_artifacts(world_name, retry_handler, sifted)
                    return {"name": world_name, "summary": sifted, "status": "PARTIAL"}
            
        await save_audit_artifacts(world_name, retry_handler, retry_handler.last_result or "")
        return {"name": world_name, "summary": retry_handler.last_result, "status": "PARTIAL"}
        
    except Exception as e:
        exec_service.log_transition(run_id, "Research Unit", f"Agent failed for {world_name}: {str(e)}", "FAILED", {})
        raise e
        
    except Exception as e:
        exec_service.log_transition(run_id, "Research Unit", f"Agent failed for {world_name}: {str(e)}", "FAILED", {})
        raise e
