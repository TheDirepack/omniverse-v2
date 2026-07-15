import asyncio
import json
from typing import Any

from app.agents.prompts import get_critic_prompt, get_researcher_prompt
from app.core.agent_config import get_tools_for_agent
from app.core.agent_engine import Capability, run_agent
from app.core.context import set_current_universe
from app.core.domain import ResearchTarget
from app.core.retry_handler import RetryHandler
from app.core.runtime_state import is_aborted
from app.core.validation import audit_success
from app.core.validators import validate_research_json
from app.services.execution_service import ExecutionService
from app.services.knowledge_retriever import KnowledgeRetrieverService
from app.services.research_workspace import WorkspaceService
from app.services.settings_service import SettingsService
from app.services.tiering_service import TieringService
from app.services.universe_service import UniverseService


class UniverseNotFoundError(ValueError):
    def __init__(self, uuid):
        super().__init__(f"Universe {uuid} not found")


async def save_audit_artifacts(
    universe_uuid: str,
    retry_handler: RetryHandler,
    final_result: str,
    workspace_service: WorkspaceService
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


class WorldResearcher:
    def __init__(self, target: ResearchTarget, run_id: str, focus: str | None = None):
        self.target = target
        self.run_id = run_id
        self.focus = focus

        self.uni_service = UniverseService()
        self.tier_service = TieringService()
        self.settings_service = SettingsService()
        self.retriever = KnowledgeRetrieverService()
        self.workspace_service = WorkspaceService()
        self.exec_service = ExecutionService()

    async def research(self) -> dict[str, Any]:
        universe = self.uni_service.get_universe_by_uuid(self.target.uuid)
        if not universe:
            raise UniverseNotFoundError(self.target.uuid)

        self.tier_service.clear_world_tier(universe.id)
        world_name = universe.name

        try:
            stage_label = f"{world_name} focused on {self.focus}" if self.focus else world_name
            set_current_universe(world_name)

            self.exec_service.log_transition(
                self.run_id,
                "Research Unit",
                f"Initiating incremental research for world: {stage_label}",
                "RESEARCHING",
                {}
            )

            researcher_tools = get_tools_for_agent("Researcher")
            auditor_tools = ["fetchPage", "compareSourceFreshness", "loadNotebookEntry", "queryArtifacts"]

            # Context Gathering
            context = await self._gather_universe_context(universe)

            # Configure Loop
            max_iterations_setting = self.settings_service.get_setting("MAX_RESEARCH_ITERATIONS")
            max_iterations = (
                int(max_iterations_setting.value)
                if max_iterations_setting and max_iterations_setting.value
                else 2
            )

            retry_handler = RetryHandler(max_iterations=max_iterations)
            loop_history = []

            while retry_handler.current_iteration < retry_handler.max_iterations:
                # Researcher Turn
                _, result, turn_history, researcher_system_prompt = await self._execute_research_iteration(
                    world_name, researcher_tools, retry_handler, loop_history, context
                )
                loop_history = turn_history
                if await is_aborted(self.run_id):
                    raise RuntimeError("Aborted")

                # Deterministic JSON Validation
                try:
                    parsed_result = json.loads(result)
                    is_valid, val_errors = validate_research_json(parsed_result)
                    if not is_valid:
                        deterministic_critique = json.dumps({
                            "Verification_Status": "Revision_Required",
                            "Correction_Queue": [
                                {"Error_Type": "Schema", "Issue": err, "Required_Fix": "Fix JSON schema violation"}
                                for err in val_errors
                            ]
                        })
                        retry_handler.update_state(result, deterministic_critique, turn_history)
                        continue
                except json.JSONDecodeError:
                    deterministic_critique = json.dumps({
                        "Verification_Status": "Revision_Required",
                        "Correction_Queue": [
                            {"Error_Type": "Schema", "Issue": "Invalid JSON", "Required_Fix": "Return parseable JSON"}
                        ]
                    })
                    retry_handler.update_state(result, deterministic_critique, turn_history)
                    continue

                # Critic Audit
                _success, critique, auditor_history = await self._perform_audit(
                    result, researcher_system_prompt, retry_handler, loop_history, auditor_tools
                )
                loop_history = auditor_history
                if await is_aborted(self.run_id):
                    raise RuntimeError("Aborted")

                if audit_success(critique):
                    await save_audit_artifacts(self.target.uuid, retry_handler, result, self.workspace_service)
                    return {"uuid": self.target.uuid, "name": world_name, "summary": result, "status": "VERIFIED"}

                # Feedback Generation
                feedback = self._handle_audit_failure(critique)
                retry_handler.update_state(result, feedback, turn_history)

            # Final result after max iterations
            await save_audit_artifacts(
                self.target.uuid, retry_handler, retry_handler.last_result or "", self.workspace_service
            )
            return {
                "uuid": self.target.uuid,
                "name": world_name,
                "summary": retry_handler.last_result,
                "status": "PARTIAL",
            }

        except Exception as e:
            self.exec_service.log_transition(
                self.run_id, "Research Unit", f"Agent failed for {world_name}: {e!s}", "FAILED", {}
            )
            raise
        finally:
            self.workspace_service.session.close()

    async def _gather_universe_context(self, universe) -> dict[str, str]:
        universe_id = universe.id
        claims = self.retriever.get_semantic_claims(universe_id)
        verified_claims_str = "\n".join(
            [f"({c['subject']} --{c['predicate']}--> {c['object']}) | ref: {c['reference'] or 'N/A'}" for c in claims]
        )
        knowledge_graph_str = json.dumps(self.retriever.get_universe_knowledge_graph(universe_id), indent=2)

        related_ids = []
        if universe.parent_id:
            related_ids.append(universe.parent_id)
        children = self.uni_service.get_children(universe.id)
        related_ids.extend([c.id for c in children])

        multiverse_leads_str = ""
        multiverse_kg_str = ""
        if related_ids:
            async def fetch_related_data(rid):
                rel_u = self.uni_service.get_universe_by_id(rid)
                if not rel_u:
                    return None
                return {
                    "name": rel_u.name,
                    "claims": self.retriever.get_semantic_claims(rid),
                    "kg": self.retriever.get_universe_knowledge_graph(rid),
                }

            results = await asyncio.gather(*(fetch_related_data(rid) for rid in related_ids))
            rel_claims = []
            rel_kgs = []
            for res in results:
                if res:
                    if res["claims"]:
                        rel_claims.append(
                            f"--- {res['name']} ---\n"
                            + "\n".join([f"({cl['subject']} --{cl['predicate']}--> {cl['object']}) | ref: {cl['reference'] or 'N/A'}" for cl in res["claims"]])
                        )
                    if res["kg"]:
                        rel_kgs.append(f"--- {res['name']} ---\n{json.dumps(res['kg'], indent=2)}")
            multiverse_leads_str = "\n\n".join(rel_claims)
            multiverse_kg_str = "\n\n".join(rel_kgs)

        return {
            "verified_claims": verified_claims_str,
            "knowledge_graph": knowledge_graph_str,
            "multiverse_leads": multiverse_leads_str,
            "multiverse_kg": multiverse_kg_str,
        }

    async def _execute_research_iteration(
        self,
        world_name: str,
        researcher_tools: list[str],
        retry_handler: RetryHandler,
        loop_history: list,
        context: dict[str, str],
    ) -> tuple[bool, str, list, str]:
        i = retry_handler.iteration_count
        research_queue = retry_handler.get_research_queue()
        feedback_summary = retry_handler.get_feedback_summary()

        workspace_index = self.workspace_service.get_full_workspace_index(self.target.uuid)
        notebook_content = self.workspace_service.get_notebook_content(self.run_id, self.target.uuid)
        notebook_section = f"\n\n### CURRENT WORKING NOTES (From Research Notebook):\n{notebook_content or 'No notes yet.'}"

        researcher_prompt = get_researcher_prompt(
            entity=world_name,
            requirements="Collect comprehensive canonical wiki data.",
            focus=self.focus,
            previous_dataset=retry_handler.last_result,
            outstanding_corrections=feedback_summary,
            verified_claims=context["verified_claims"] if i == 0 else None,
            knowledge_graph=context["knowledge_graph"] if i == 0 else None,
            multiverse_leads=context["multiverse_leads"] if i == 0 else None,
            multiverse_kg=context["multiverse_kg"] if i == 0 else None,
            workspace_index=workspace_index,
        )

        user_prompt = researcher_prompt["user"] + notebook_section
        if research_queue:
            user_prompt += f"\n\nLEADS: {research_queue}\nPrioritize these."

        max_turns_setting = self.settings_service.get_setting("MAX_RESEARCH_TURNS")
        max_turns = (
            int(max_turns_setting.value)
            if max_turns_setting and max_turns_setting.value
            else 50
        )

        min_turns_setting = self.settings_service.get_setting("MIN_RESEARCH_TURNS")
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
            run_id=self.run_id,
            tools_names=researcher_tools,
            submit_tool_name="submit_research",
            max_turns=max_turns,
            min_turns=min_turns,
            history=loop_history,
            required_capabilities={
                Capability.READ_MAIN_DB,
                Capability.READ_WORKSPACE,
                Capability.WRITE_WORKSPACE,
                Capability.ACQUISITION,
            },
        )
        return success, result, turn_history, researcher_prompt["system"]

    async def _perform_audit(
        self,
        result: str,
        researcher_system_prompt: str,
        retry_handler: RetryHandler,
        loop_history: list,
        auditor_tools: list[str],
    ) -> tuple[bool, str, list]:
        feedback_summary = retry_handler.get_feedback_summary()
        critic_prompt = get_critic_prompt(
            data=result,
            criteria=researcher_system_prompt,
            previous_corrections=feedback_summary,
            is_final_attempt=retry_handler.is_final_attempt(),
        )
        _success, critique, auditor_history = await run_agent(
            agent_name="Logic Auditor",
            system_prompt=critic_prompt["system"],
            user_prompt=critic_prompt["user"],
            step=f"Audit (Attempt {retry_handler.iteration_count})",
            run_id=self.run_id,
            tools_names=auditor_tools,
            submit_tool_name="submit_audit",
            history=loop_history,
            required_capabilities={
                Capability.READ_MAIN_DB,
                Capability.READ_WORKSPACE,
                Capability.WRITE_WORKSPACE,
            },
        )
        return _success, critique, auditor_history

    def _handle_audit_failure(self, critique: str) -> str:
        try:
            critique_json = json.loads(critique)
            corrections = critique_json.get("Correction_Queue", [])
            feedback = "\n".join(
                [f"[{c.get('Error_Type')}] {c.get('Issue')} -> Fix: {c.get('Required_Fix')}" for c in corrections]
            )
            if not feedback:
                feedback = "General improvements needed."
        except:
            feedback = critique
        return feedback


async def research_single_world(
    target: ResearchTarget,
    run_id: str,
    focus: str | None = None,
) -> dict[str, Any]:
    researcher = WorldResearcher(target, run_id, focus)
    return await researcher.research()


