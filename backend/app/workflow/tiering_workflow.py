import json
import logging
import re
from typing import Any

from sqlmodel import Session

from app.agents.prompts import (
    get_architect_prompt,
    get_rubric_amendment_prompt,
    get_stability_prompt,
)
from app.core.agent_engine import run_agent
from app.db.session import engine
from app.services.execution_service import ExecutionService
from app.services.settings_service import SettingsService
from app.services.tiering_service import TieringService
from app.services.universe_service import UniverseService


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
        if (
            line.startswith("SUCCESS")
            or line.startswith("VERIFIED")
            or line.startswith("STATUS: SUCCESS")
            or line.startswith("STATUS: VERIFIED")
        ):
            return True

    return False


async def _audit_tier_system(
    tier_system_definition: str, dataset: str, run_id: str
) -> tuple[bool, str]:
    critic_system_prompt = """### ROLE
Strict Logic Auditor. Your goal is to find flaws in the proposed Tier System.

PROCESS
1. Analyze the provided Tier System and the consolidated dataset.
2. Use `fetchPage` and `webSearch` to verify specific threshold claims.
3. Look for semantic overlaps, gaps in scaling, or contradictions with canonical data.
4. Check that thresholds are phrased as durable, measurable properties (not as
   lists of    specific worlds), since this rubric must remain valid for worlds
   not yet in the database.

5. Specifically check if the relative progression (Tier 0 lowest, Tier 10 highest) is
   logically sound.

OUTPUT
Call `submit_audit` with a STATUS (SUCCESS/REVISION_REQUIRED) and a detailed
Correction Queue.
"""
    critic_user_prompt = (
        f"Proposed Tier System:\n{tier_system_definition}\n\nDataset:\n{dataset}"
    )

    audit_result, _ = await run_agent(
        agent_name="Logic Auditor",
        system_prompt=critic_system_prompt,
        user_prompt=critic_user_prompt,
        step="Audit",
        run_id=run_id,
        tools_names=["fetchPage"],
        submit_tool_name="submit_audit",
    )
    return audit_success(audit_result), audit_result


def _parse_stability_result(stability_result: str) -> dict[str, Any]:
    upper = stability_result.upper()
    status = "UNKNOWN"
    if "STATUS: STABLE" in upper:
        status = "STABLE"
    elif "STATUS: ANOMALY" in upper:
        status = "ANOMALY"
    elif "STATUS: INSUFFICIENT_DATA" in upper:
        status = "INSUFFICIENT"

    tier_num = None
    tier_match = re.search(r"TIER:\s*(\d+)", stability_result, re.IGNORECASE)
    if tier_match:
        try:
            tier_num = max(0, min(10, int(tier_match.group(1))))
        except Exception as e:
            logging.exception(f"Failed to parse tier number from stability result: {e}")

    return {"status": status, "tier": tier_num, "justification": stability_result}


MAX_ARCHITECTURE_ATTEMPTS = 5


async def architecture_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state.get("run_id")
    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")

    anomalies = state.get("anomalies", [])
    attempt = state.get("architecture_attempts", 0) + 1
    exec_service = ExecutionService()
    tier_service = TieringService()
    uni_service = UniverseService()
    settings_service = SettingsService()

    if attempt > MAX_ARCHITECTURE_ATTEMPTS:
        exec_service.log_transition(
            run_id,
            "Manager",
            (
                f"Architecture/critic loop exceeded {MAX_ARCHITECTURE_ATTEMPTS} "
                "attempts without reaching a stable, audited tier system. "
                f"Aborting run to avoid an unbounded retry loop. "
                f"Last anomalies: {anomalies}"
            ),
            "FAILED",
            state,
        )

        raise RuntimeError(
            f"Architecture design failed to stabilize after "
            f"{MAX_ARCHITECTURE_ATTEMPTS} attempts."
        )

    dataset = ""
    with Session(engine):
        setting = settings_service.get_setting("CONSOLIDATED_DATASET")
        if setting:
            dataset = setting.value
        active_rubric = tier_service.repo.get_active_rubric()

    if active_rubric is None:
        exec_service.log_transition(
            run_id,
            "Tier Architect",
            f"No persistent rubric found. Bootstrapping tier rubric from scratch "
            f"(attempt {attempt}/{MAX_ARCHITECTURE_ATTEMPTS}).",
            "IN_PROGRESS",
            state,
        )

        architect_prompts = get_architect_prompt(dataset, anomalies)
        tier_system_definition, _ = await run_agent(
            agent_name="Tier Architect",
            system_prompt=architect_prompts["system"],
            user_prompt=architect_prompts["user"],
            step="Architecture",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_architecture",
        )

        is_success, audit_result = await _audit_tier_system(
            tier_system_definition, dataset, run_id
        )
        exec_service.log_transition(
            run_id,
            "Logic Auditor",
            f"Audited bootstrap Tier Rubric. Status: "
            f"{'SUCCESS' if is_success else 'REVISION_REQUIRED'}",
            "IN_PROGRESS",
            state,
        )

        if not is_success:
            return {
                "anomalies": [f"System Design Error: {audit_result}"],
                "system_stable": False,
                "active_task": "RE_ARCHITECTURE",
                "architecture_attempts": attempt,
            }

        active_rubric = tier_service.create_rubric(tier_system_definition)

    rubric_id = active_rubric.id
    rubric_text = active_rubric.system_definition

    exec_service.log_transition(
        run_id,
        "Stability Unit",
        f"Slotting worlds into persistent rubric v{active_rubric.version}",
        "IN_PROGRESS",
        state,
    )

    world_tier_mappings = []
    anomalous = []

    verified_world_names = state.get("verified_worlds", [])
    universes = uni_service.repo.get_by_names(verified_world_names)

    for universe in universes:
        assert universe.id is not None
        summary = universe.summary or "No summary available."
        stability_prompts = get_stability_prompt(summary, rubric_text)

        stability_result, _ = await run_agent(
            agent_name="Stability Unit",
            system_prompt=stability_prompts["system"],
            user_prompt=stability_prompts["user"],
            step="Stability Check",
            run_id=run_id,
            tools_names=["webSearch", "fetchPage"],
            submit_tool_name="submit_stability",
        )

        status_match = re.search(
            r"STATUS:\s*(STABLE|ANOMALY|INSUFFICIENT_DATA)",
            stability_result,
            re.IGNORECASE,
        )
        status = status_match.group(1).upper() if status_match else "UNKNOWN"
        is_stable = status == "STABLE"

        tier_num = 11
        tier_match = re.search(r"TIER:\s*(\d+)", stability_result, re.IGNORECASE)
        if tier_match:
            try:
                tier_num = int(tier_match.group(1))
            except ValueError:
                exec_service.log_transition(
                    run_id,
                    "Stability Unit",
                    f"Could not parse TIER value for {universe.name}, "
                    f"defaulting to Tier 11.",
                    "IN_PROGRESS",
                    state,
                )
        else:
            exec_service.log_transition(
                run_id,
                "Stability Unit",
                    f"No TIER field found in stability output for {universe.name}, "
                    f"defaulting to Tier 11.",

                "IN_PROGRESS",
                state,
            )

        if is_stable:
            world_tier_mappings.append(
                {
                    "universe_id": universe.id,
                    "tier": tier_num,
                    "justification": stability_result,
                }
            )
        elif status == "INSUFFICIENT_DATA":
            continue
        else:
            assert universe.id is not None
            tier_service.create_anomaly(universe.id, stability_result)
            anomalous.append((universe, stability_result))

    if anomalous:
        retries = state.get("architecture_retries", 0) + 1
        anomaly_descriptions = [f"{u.name}: {res}" for u, res in anomalous]

        if retries >= 3:
            exec_service.log_transition(
                run_id,
                "Manager",
                f"Max amendment attempts reached for {len(anomalous)} anomalies. "
                "Recording as untiered and proceeding.",
                "IN_PROGRESS",
                state,
            )
            for universe, res in anomalous:
                assert universe.id is not None
                tier_service.clear_world_tier(universe.id)
                tier_service.slot_world(universe.id, rubric_id, -1, res)
            for wt in world_tier_mappings:
                assert wt["universe_id"] is not None
                tier_service.slot_world(
                    wt["universe_id"], rubric_id, wt["tier"], wt["justification"]
                )

            return {
                "anomalies": anomaly_descriptions,
                "system_stable": False,
                "current_tier_system": rubric_text,
                "active_task": "EXTRAPOLATION",
                "architecture_retries": retries,
            }

        exec_service.log_transition(
            run_id,
            "Rubric Steward",
            f"{len(anomalous)} world(s) don't fit the persistent rubric. "
            "Proposing minimal amendment.",
            "IN_PROGRESS",
            state,
        )

        amendment_prompt = get_rubric_amendment_prompt(
            rubric_text, dataset, anomaly_descriptions
        )
        amended_definition, _ = await run_agent(
            agent_name="Rubric Steward",
            system_prompt=amendment_prompt["system"],
            user_prompt=amendment_prompt["user"],
            step="Rubric Amendment",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_architecture",
        )

        is_success, audit_result = await _audit_tier_system(
            amended_definition, dataset, run_id
        )
        exec_service.log_transition(
            run_id,
            "Logic Auditor",
            f"Audited rubric amendment. Status: "
            f"{'SUCCESS' if is_success else 'REVISION_REQUIRED'}",
            "IN_PROGRESS",
            state,
        )

        if not is_success:
            return {
                "anomalies": [
                    f"Rubric Amendment Error: {audit_result}",
                    *anomaly_descriptions,
                ],
                "system_stable": False,
                "active_task": "RE_ARCHITECTURE",
                "architecture_attempts": attempt,
            }

        # Persist confirmed worlds under the OLD rubric first
        for wt in world_tier_mappings:
            assert wt["universe_id"] is not None
            tier_service.slot_world(
                wt["universe_id"], rubric_id, wt["tier"], wt["justification"]
            )

        new_rubric = tier_service.amend_rubric(
            rubric_id, amended_definition, "; ".join(anomaly_descriptions)
        )
        new_rubric_id = new_rubric.id
        new_rubric_text = new_rubric.system_definition
        new_rubric_version = new_rubric.version

        exec_service.log_transition(
            run_id,
            "Stability Unit",
            f"Re-slotting {len(anomalous)} world(s) against amended rubric "
            f"v{new_rubric_version}",
            "IN_PROGRESS",
            state,
        )
        for universe, _prev_result in anomalous:
            stability_prompts = get_stability_prompt(
                universe.summary or "", new_rubric_text
            )
            stability_result, _ = await run_agent(
                agent_name="Stability Unit",
                system_prompt=stability_prompts["system"],
                user_prompt=stability_prompts["user"],
                step="Stability Re-check",
                run_id=run_id,
                tools_names=["webSearch", "fetchPage"],
                submit_tool_name="submit_stability",
            )
            parsed = _parse_stability_result(stability_result)
            tier_val = parsed["tier"] if parsed["tier"] is not None else -1
            assert universe.id is not None
            tier_service.slot_world(
                universe.id, new_rubric_id, tier_val, parsed["justification"]
            )

        exec_service.log_transition(
            run_id,
            "Manager",
            f"Rubric amended to v{new_rubric_version}. Tiering complete.",
            "COMPLETED",
            state,
        )

        next_task = (
            "EXTRAPOLATION" if not state.get("is_focused_search") else "FINISHED"
        )
        return {
            "current_tier_system": new_rubric_text,
            "system_stable": True,
            "active_task": next_task,
        }

    for wt in world_tier_mappings:
        tier_service.slot_world(
            wt["universe_id"], rubric_id, wt["tier"], wt["justification"]
        )

    exec_service.log_transition(
        run_id,
        "Manager",
        "Completed tiering under persistent rubric.",
        "COMPLETED",
        state,
    )

    next_task = "EXTRAPOLATION" if not state.get("is_focused_search") else "FINISHED"
    return {
        "current_tier_system": rubric_text,
        "system_stable": True,
        "active_task": next_task,
        "architecture_attempts": 0,
    }
