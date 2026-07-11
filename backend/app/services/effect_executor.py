import asyncio
import json
from typing import Any

from app.agents.prompts import (
    get_cleanup_prompt,
    get_db_agent_prompt,
    get_facilitator_prompt,
)
from app.core.agent_engine import Capability, run_agent
from app.core.context import set_current_universe
from app.research.researcher import research_single_world
from app.research.summarizer import summarize_universe
from app.services.execution_service import ExecutionService
from app.services.settings_service import SettingsService
from app.services.universe_service import UniverseService


class EffectExecutor:
    def __init__(self):
        self.exec_service = ExecutionService()
        self.settings_service = SettingsService()
        self.uni_service = UniverseService()

    async def execute(self, state: dict[str, Any]):
        effects = state.get("pending_effects", [])
        if not effects:
            return state

        run_id = state.get("run_id")

        # Create a copy of state to update and return
        new_state = state.copy()
        new_state["pending_effects"] = []

        for effect in effects:
            eff_type = effect.get("type")
            params = effect.get("params", {})

            try:
                if eff_type == "log_transition":
                    self.exec_service.log_transition(
                        run_id,
                        params["node"],
                        params["thought"],
                        params["status"],
                        state,
                    )

                elif eff_type == "research_worlds":
                    target_worlds = params["target_worlds"]
                    focused_features = params.get("focused_features")
                    focus_str = (
                        ", ".join(focused_features) if focused_features else None
                    )

                    setting = self.settings_service.get_setting("MAX_PARALLEL_AGENTS")
                    batch_size = int(setting.value) if setting and setting.value else 5
                    if batch_size <= 0:
                        batch_size = 1

                    successful_results = []
                    errors = []
                    verified_worlds = []

                    for i in range(0, len(target_worlds), batch_size):
                        batch = target_worlds[i : i + batch_size]
                        tasks = [
                            research_single_world(world, run_id, focus=focus_str)
                            for world in batch
                        ]
                        batch_results = await asyncio.gather(
                            *tasks, return_exceptions=True
                        )

                        for r in batch_results:
                            if isinstance(r, Exception):
                                errors.append(str(r))
                            elif isinstance(r, dict):
                                successful_results.append(r)
                                verified_worlds.append(r["uuid"])

                    new_state["research_results"] = successful_results
                    new_state["verified_worlds"] = verified_worlds
                    new_state["errors"] = errors

                elif eff_type == "facilitate_results":
                    research_results = state.get("research_results", [])
                    facilitated_results = []
                    for result in research_results:
                        world_name = result["name"]
                        dataset = result["summary"]
                        prompt = get_facilitator_prompt(dataset, world_name)

                        success, final_ans, _ = await run_agent(
                            agent_name="Facilitator",
                            system_prompt=prompt["system"],
                            user_prompt=prompt["user"],
                            step=f"Facilitate {world_name}",
                            run_id=run_id,
                            tools_names=[],
                            submit_tool_name="submit_facilitation",
                            required_capabilities={Capability.READ_MAIN_DB},
                        )

                        if success:
                            try:
                                facilitated_data = json.loads(final_ans)
                                result["graduated_claims"] = facilitated_data.get(
                                    "graduated_claims", []
                                )
                                result["retained_claims"] = facilitated_data.get(
                                    "retained_claims", []
                                )
                                result["facilitation_summary"] = facilitated_data.get(
                                    "decision_summary", ""
                                )
                            except json.JSONDecodeError:
                                result["facilitation_error"] = (
                                    "Failed to parse facilitator output"
                                )
                        else:
                            result["facilitation_error"] = (
                                f"Facilitation failed: {final_ans}"
                            )
                        facilitated_results.append(result)

                    new_state["research_results"] = facilitated_results

                elif eff_type == "integrate_data":
                    research_results = state.get("research_results", [])
                    for result in research_results:
                        world_name = result["name"]
                        graduated_claims = result.get("graduated_claims", [])
                        if not graduated_claims:
                            continue

                        verified_data = json.dumps(graduated_claims)
                        status = result.get("status", "VERIFIED")
                        prompt = get_db_agent_prompt()
                        user_prompt_data = (
                            f"Universe: {world_name}\n"
                            f"Verification Status: {status}\n\n"
                            f"Verified Research Data:\n{verified_data}"
                        )

                        set_current_universe(world_name)

                        success, final_ans, history = await run_agent(
                            agent_name="DB Architect",
                            system_prompt=prompt["system"],
                            user_prompt=user_prompt_data,
                            step=f"Integrate {world_name}",
                            run_id=run_id,
                            tools_names=["queryClaims", "upsertClaims"],
                            submit_tool_name="submit_integration",
                            required_capabilities={
                                Capability.READ_MAIN_DB,
                                Capability.WRITE_MAIN_DB,
                                Capability.READ_WORKSPACE,
                                Capability.WRITE_WORKSPACE,
                            },
                        )

                        if success:
                            cleanup_prompt = get_cleanup_prompt()
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
                                required_capabilities={
                                    Capability.READ_MAIN_DB,
                                    Capability.READ_WORKSPACE,
                                    Capability.WRITE_WORKSPACE,
                                },
                            )

                    universes = self.uni_service.get_by_names(
                        [r["name"] for r in research_results]
                    )
                    for u in universes:
                        u.is_explored = True
                    self.uni_service.update_batch(universes)

                elif eff_type == "summarize_universes":
                    verified_worlds = state.get("verified_worlds", [])
                    universes = self.uni_service.get_by_names(verified_worlds)
                    universe_ids = [u.id for u in universes]
                    tasks = [summarize_universe(uid, run_id) for uid in universe_ids]
                    await asyncio.gather(*tasks)

            except Exception as e:
                # In a real system, we might want to handle this differently
                # For now, just add to errors
                if "errors" not in new_state:
                    new_state["errors"] = []
                new_state["errors"].append(f"Effect {eff_type} failed: {e!s}")

        return new_state
