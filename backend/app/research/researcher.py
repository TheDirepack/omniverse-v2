import json
from typing import Any

from app.agents.prompts import get_critic_prompt, get_researcher_prompt
from app.core.agent_engine import run_agent
from app.core.context import set_current_universe
from app.core.retry_handler import RetryHandler
from app.core.validators import validate_research_json
from app.core.validation import audit_success
from app.services.execution_service import ExecutionService


from app.core.validation import audit_success
from app.services.execution_service import ExecutionService

async def save_audit_artifacts(
    _world_name: str, retry_handler: RetryHandler, final_result: str
):
    from app.core.tools import tool_save_unconfirmed_claim

    # Save audit history
    await tool_save_unconfirmed_claim(
        {
            "subject": _world_name,
            "predicate": "HAS_AUDIT_HISTORY",
            "object_val": json.dumps(retry_handler.feedback_history, indent=2),
            "confidence": "high",
        }
    )

    # Save final knowledge graph
    await tool_save_unconfirmed_claim(
        {
            "subject": _world_name,
            "predicate": "HAS_FINAL_KNOWLEDGE_GRAPH",
            "object_val": final_result,
            "confidence": "high",
        }
    )

    # Save final knowledge graph
    await tool_save_unconfirmed_claim(
        {
            "subject": _world_name,
            "predicate": "HAS_FINAL_KNOWLEDGE_GRAPH",
            "object_val": final_result,
            "confidence": "high",
        }
    )


async def research_single_world(
    universe_uuid: str,
    run_id: str,
    focus: str | None = None,
) -> dict[str, Any]:
    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")

    from app.services.knowledge_retriever import KnowledgeRetrieverService
    from app.services.settings_service import SettingsService
    from app.services.tiering_service import TieringService
    from app.services.universe_service import UniverseService

    uni_service = UniverseService()
    tier_service = TieringService()
    settings_service = SettingsService()
    retriever = KnowledgeRetrieverService()

    universe = uni_service.get_universe_by_uuid(universe_uuid)
    if not universe:
        raise ValueError(f"Universe with UUID {universe_uuid} not found.")

    if universe:
        tier_service.clear_world_tier(universe.id)

    world_name = universe.name
    stage_label = f"{world_name} focused on {focus}" if focus else world_name
    set_current_universe(world_name)

    exec_service = ExecutionService()
    exec_service.log_transition(
        run_id,
        "Research Unit",
        f"Initiating incremental research for world: {stage_label}",
        "RESEARCHING",
        {},
    )

    researcher_tools = [
        "webSearch",
        "fetchPage",
        "ocrImage",
        "compareSourceFreshness",
        "queryClaims",
        "queryUnconfirmedClaims",
        "saveUnconfirmedClaim",
    ]
    auditor_tools = [
        "fetchPage",
        "compareSourceFreshness",
        "queryClaims",
        "queryUnconfirmedClaims",
    ]

    # Fetch existing knowledge for the first prompt
    universe_id = universe.id if universe else None
    verified_claims_str = ""
    knowledge_graph_str = ""
    multiverse_leads_str = ""
    multiverse_kg_str = ""

    if universe_id:
        # Current universe context
        claims = retriever.get_semantic_claims(universe_id)
        verified_claims_str = "\n".join(
            [
                f"({c['subject']} --{c['predicate']}--> {c['object']}) | "
                f"ref: {c['reference'] or 'N/A'}"
                for c in claims
            ]
        )
        knowledge_graph_str = json.dumps(
            retriever.get_universe_knowledge_graph(universe_id), indent=2
        )

        # Multiverse context: Parent and Children
        related_ids = []
        if universe.parent_id:
            related_ids.append(universe.parent_id)
        
        children = uni_service.get_children(universe.id)
        related_ids.extend([c.id for c in children])

        if related_ids:
            rel_claims = []
            rel_kgs = []
            for rid in related_ids:
                rel_u = uni_service.get_universe_by_id(rid)
                if rel_u:
                    c = retriever.get_semantic_claims(rid)
                    if c:
                        rel_claims.append(f"--- {rel_u.name} ---\n" + "\n".join(
                            [f"({cl['subject']} --{cl['predicate']}--> {cl['object']}) | ref: {cl['reference'] or 'N/A'}" for cl in c]
                        ))
                    kg = retriever.get_universe_knowledge_graph(rid)
                    if kg:
                        rel_kgs.append(f"--- {rel_u.name} ---\n{json.dumps(kg, indent=2)}")
            
            multiverse_leads_str = "\n\n".join(rel_claims)
            multiverse_kg_str = "\n\n".join(rel_kgs)

    retry_handler = RetryHandler(max_iterations=3)

    try:
        while retry_handler.current_iteration < retry_handler.max_iterations:
            i = retry_handler.iteration_count
            research_queue = retry_handler.get_research_queue()
            feedback_summary = retry_handler.get_feedback_summary()

            # Also fetch unconfirmed data for the prompt
            from app.core.tools import tool_query_unconfirmed_claims

            unconfirmed_data = await tool_query_unconfirmed_claims({})

            researcher_prompt = get_researcher_prompt(
                entity=world_name,
                requirements="Collect comprehensive canonical wiki data.",
                focus=focus,
                previous_dataset=retry_handler.last_result,
                outstanding_corrections=feedback_summary,
                unconfirmed_data=unconfirmed_data,
                verified_claims=verified_claims_str if i == 0 else None,
                knowledge_graph=knowledge_graph_str if i == 0 else None,
                multiverse_leads=multiverse_leads_str if i == 0 else None,
                multiverse_kg=multiverse_kg_str if i == 0 else None,
            )

            user_prompt = researcher_prompt["user"]

            if research_queue and feedback_summary == "None":
                user_prompt += (
                    f"\n\n{research_queue}\n\nPrioritize these leads in your tool use."
                )
            elif research_queue:
                user_prompt += (
                    "\n\nSECONDARY LEADS (Address only after all "
                    "corrections are resolved):\n"
                    f"{research_queue}"
                )

            min_turns_setting = settings_service.get_setting("MIN_RESEARCH_TURNS")
            min_turns = (
                int(min_turns_setting.value)
                if min_turns_setting and min_turns_setting.value
                else 6
            )

            success, result, turn_history = await run_agent(
                agent_name="Researcher",
                system_prompt=researcher_prompt["system"],
                user_prompt=user_prompt,
                step=f"Research (Attempt {i})",
                run_id=run_id,
                tools_names=researcher_tools,
                max_turns=min_turns,
            )



            # Deterministic Validation
            try:
                parsed_result = json.loads(result)
                is_valid, val_errors = validate_research_json(parsed_result)
                if not is_valid:
                    deterministic_critique = json.dumps(
                        {
                            "Verification_Status": "Revision_Required",
                            "Correction_Queue": [
                                {
                                    "Error_Type": "Schema",
                                    "Issue": err,
                                    "Required_Fix": "Fix JSON schema violation",
                                }
                                for err in val_errors
                            ],
                        }
                    )
                    if val_errors:
                        retry_handler.update_state(
                            result, deterministic_critique, turn_history
                        )
                        if retry_handler.is_final_attempt():
                            sifted = retry_handler.handle_final_attempt(
                                deterministic_critique
                            )
                            if sifted:
                                await save_audit_artifacts(
                                    world_name, retry_handler, sifted
                                )
                                return {
                                    "name": world_name,
                                    "summary": sifted,
                                    "status": "PARTIAL",
                                }
                        continue
            except json.JSONDecodeError:
                deterministic_critique = json.dumps(
                    {
                        "Verification_Status": "Revision_Required",
                        "Correction_Queue": [
                            {
                                "Error_Type": "Schema",
                                "Issue": "Invalid JSON",
                                "Required_Fix": "Return a parseable JSON object",
                            }
                        ],
                    }
                )
                retry_handler.update_state(result, deterministic_critique, turn_history)
                if retry_handler.is_final_attempt():
                    sifted = retry_handler.handle_final_attempt(deterministic_critique)
                    if sifted:
                        await save_audit_artifacts(world_name, retry_handler, sifted)
                        return {
                            "name": world_name,
                            "summary": sifted,
                            "status": "PARTIAL",
                        }
                continue

            critic_prompt = get_critic_prompt(
                data=result,
                criteria=researcher_prompt["system"],
                previous_corrections=feedback_summary,
                is_final_attempt=retry_handler.is_final_attempt(),
            )

            success, critique, _ = await run_agent(
                agent_name="Logic Auditor",
                system_prompt=critic_prompt["system"],
                user_prompt=critic_prompt["user"],
                step=f"Audit (Attempt {i})",
                run_id=run_id,
                tools_names=auditor_tools,
                submit_tool_name="submit_audit",
            )

            if audit_success(critique):
                import logging
                logging.getLogger(__name__).debug(f"audit_success(critique) is True for {critique}")
                await save_audit_artifacts(world_name, retry_handler, result)
                return {"name": world_name, "summary": result, "status": "VERIFIED"}
            import logging
            logging.getLogger(__name__).debug(f"audit_success(critique) is False for {critique}")
            retry_handler.update_state(result, critique, turn_history)

            if retry_handler.is_final_attempt():
                sifted = retry_handler.handle_final_attempt(critique)
                if sifted:
                    await save_audit_artifacts(world_name, retry_handler, sifted)
                    return {
                        "name": world_name,
                        "summary": sifted,
                        "status": "PARTIAL",
                    }

        await save_audit_artifacts(
            world_name, retry_handler, retry_handler.last_result or ""
        )
        return {
            "name": world_name,
            "summary": retry_handler.last_result,
            "status": "PARTIAL",
        }

    except Exception as e:
        exec_service.log_transition(
            run_id,
            "Research Unit",
            f"Agent failed for {world_name}: {e!s}",
            "FAILED",
            {},
        )
        raise e
