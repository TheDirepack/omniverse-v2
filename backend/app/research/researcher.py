import asyncio
import json
import logging
from typing import Any

from app.agents.prompts import get_critic_prompt, get_researcher_prompt
from app.core.agent_engine import Capability, run_agent
from app.core.context import set_current_universe
from app.core.domain import ResearchTarget
from app.core.retry_handler import RetryHandler
from app.core.validation import audit_success
from app.core.validators import validate_research_json


class UniverseNotFoundError(ValueError):
    def __init__(self, uuid):
        super().__init__(f"Universe {uuid} not found")

from app.services.execution_service import ExecutionService
from app.services.research_workspace import WorkspaceService


async def save_audit_artifacts(
    universe_uuid: str, retry_handler: RetryHandler, final_result: str, workspace_service: WorkspaceService
):
    # Save audit history as a notebook entry
    workspace_service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        title="Audit History",
        summary="Log of audit iterations and feedback.",
        details=json.dumps(retry_handler.feedback_history, indent=2),
        kind="Observation"
    )

    # Save final knowledge graph as a notebook entry
    workspace_service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        title="Final Knowledge Graph",
        summary="The verified consolidated data from the research cycle.",
        details=final_result,
        kind="Observation"
    )



async def research_single_world(
    target: ResearchTarget,
    run_id: str,
    focus: str | None = None,
) -> dict[str, Any]:
    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        raise RuntimeError("Aborted")

    from app.core.agent_config import get_tools_for_agent
    from app.services.knowledge_retriever import KnowledgeRetrieverService
    from app.services.settings_service import SettingsService
    from app.services.tiering_service import TieringService
    from app.services.universe_service import UniverseService

    uni_service = UniverseService()
    tier_service = TieringService()
    settings_service = SettingsService()
    retriever = KnowledgeRetrieverService()
    workspace_service = WorkspaceService()

    universe = uni_service.get_universe_by_uuid(target.uuid)
    if not universe:
        raise UniverseNotFoundError(target.uuid)

    tier_service.clear_world_tier(universe.id)

    try:
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

        # Tool definitions
        researcher_tools = get_tools_for_agent("Researcher")
        auditor_tools = get_tools_for_agent("LogicAuditor")

        auditor_tools = [
            "fetchPage",
            "compareSourceFreshness",
            "queryArtifacts",
            "queryUnconfirmedArtifacts",
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
                async def fetch_related_data(rid):
                    rel_u = uni_service.get_universe_by_id(rid)
                    if not rel_u:
                        return None

                    claims = retriever.get_semantic_claims(rid)
                    kg = retriever.get_universe_knowledge_graph(rid)

                    return {
                        "name": rel_u.name,
                        "claims": claims,
                        "kg": kg
                    }

                # Parallelize related universe fetches
                results = await asyncio.gather(
                    *(fetch_related_data(rid) for rid in related_ids)
                )

                rel_claims = []
                rel_kgs = []
                for res in results:
                    if res:
                        if res["claims"]:
                            rel_claims.append(
                                f"--- {res['name']} ---\n" + "\n".join(
                                    [
                                        f"({cl['subject']} --{cl['predicate']}--> {cl['object']}) | "
                                        f"ref: {cl['reference'] or 'N/A'}"
                                        for cl in res["claims"]
                                    ]
                                )
                            )
                        if res["kg"]:
                            rel_kgs.append(
                                f"--- {res['name']} ---\n{json.dumps(res['kg'], indent=2)}"
                            )

                multiverse_leads_str = "\n\n".join(rel_claims)
                multiverse_kg_str = "\n\n".join(rel_kgs)

        retry_handler = RetryHandler(max_iterations=3)

        # Initialize isolated loop history
        loop_history = []

        while retry_handler.current_iteration < retry_handler.max_iterations:
            i = retry_handler.iteration_count
            research_queue = retry_handler.get_research_queue()
            feedback_summary = retry_handler.get_feedback_summary()

            # Also fetch unconfirmed data for the prompt
            from app.core.tools import tool_query_unconfirmed_artifacts

            unconfirmed_data = await tool_query_unconfirmed_artifacts({})

            # Fetch indexed workspace data for the prompt
            workspace_index = workspace_service.get_full_workspace_index(target.uuid)

            # Add notebook content to the prompt to prevent redundant searching
            notebook_content = workspace_service.get_notebook_content(run_id, target.uuid)
            notebook_section = (
                f"\n\n### CURRENT WORKING NOTES (From Research Notebook):\n"
                f"{notebook_content or 'No notes yet.'}"
            )

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
                workspace_index=workspace_index,
            )

            user_prompt = researcher_prompt["user"] + notebook_section

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
                history=loop_history,
                required_capabilities={
                    Capability.READ_MAIN_DB,
                    Capability.READ_WORKSPACE,
                    Capability.WRITE_WORKSPACE,
                    Capability.ACQUISITION,
                },
            )
            loop_history.extend(turn_history)
            if await is_aborted(run_id):
                raise RuntimeError("Aborted")

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
                                    target.uuid, retry_handler, sifted, workspace_service
                                )
                                return {
                                    "uuid": target.uuid,
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
                        await save_audit_artifacts(target.uuid, retry_handler, sifted, workspace_service)
                        return {
                            "uuid": target.uuid,
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

            _success, critique, turn_history = await run_agent(
                agent_name="Logic Auditor",
                system_prompt=critic_prompt["system"],
                user_prompt=critic_prompt["user"],
                step=f"Audit (Attempt {i})",
                run_id=run_id,
                tools_names=auditor_tools,
                submit_tool_name="submit_audit",
                history=loop_history,
                required_capabilities={
                    Capability.READ_MAIN_DB,
                    Capability.READ_WORKSPACE,
                    Capability.WRITE_WORKSPACE,
                },
            )
            loop_history.extend(turn_history)
            if await is_aborted(run_id):
                raise RuntimeError("Aborted")

            if audit_success(critique):
                logging.getLogger(__name__).debug(
                    "audit_success(critique) is True for %s", critique
                )
                await save_audit_artifacts(
                    target.uuid, retry_handler, result, workspace_service
                )
                return {
                    "uuid": target.uuid,
                    "name": world_name,
                    "summary": result,
                    "status": "VERIFIED",
                }
            logging.getLogger(__name__).debug(
                "audit_success(critique) is False for %s", critique
            )
            retry_handler.update_state(result, critique, turn_history)

            if retry_handler.is_final_attempt():
                sifted = retry_handler.handle_final_attempt(critique)
                if sifted:
                    await save_audit_artifacts(
                        target.uuid, retry_handler, sifted, workspace_service
                    )
                    return {
                        "uuid": target.uuid,
                        "name": world_name,
                        "summary": sifted,
                        "status": "PARTIAL",
                    }



        try:
            await save_audit_artifacts(
                target.uuid,
                retry_handler,
                retry_handler.last_result or "",
                workspace_service,
            )
        except Exception:
            logging.getLogger(__name__).exception("Failed to save audit artifacts")
        else:
            return {
                "uuid": target.uuid,
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
        raise
    finally:
        workspace_service.session.close()
