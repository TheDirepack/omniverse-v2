from typing import Any

from app.agents.prompts import get_extrapolation_prompt, get_theory_auditor_prompt
from app.core.agent_engine import run_agent
from app.core.context import set_current_universe
from app.services.execution_service import ExecutionService
from app.services.theory_service import TheoryService
from app.services.universe_service import UniverseService


async def extrapolation_node(state: dict[str, Any]) -> dict[str, Any]:
    run_id = state.get("run_id")
    if run_id is None:
        raise RuntimeError("run_id is required in state")
    from app.core.runtime_state import is_aborted

    if await is_aborted(run_id):
        raise RuntimeError(f"Run {run_id} was aborted by user.")

    exec_service = ExecutionService()
    theory_service = TheoryService()
    uni_service = UniverseService()

    exec_service.log_transition(
        run_id,
        "Ontological Theorist",
        "Starting theoretical scaling projections",
        "IN_PROGRESS",
        state,
    )

    generated_theories = []

    verified_world_names = state.get("verified_worlds", [])
    universes = uni_service.repo.get_by_names(verified_world_names)

    for universe in universes:
        if universe.id is None:
            continue
        set_current_universe(universe.name)

        uni_context = universe.summary or "No summary recorded."

        comparison_texts = []
        for other in universes:
            if other.id == universe.id:
                continue
            comparison_texts.append(f"World: {other.name}\nSummary:\n{other.summary or 'No summary recorded.'}")

        comparison_context = "\n\n---\n\n".join(comparison_texts)

        theory_prompt = get_extrapolation_prompt(
            universe.name, uni_context, comparison_context
        )

        speculation, _ = await run_agent(
            agent_name="Ontological Theorist",
            system_prompt=theory_prompt["system"],
            user_prompt=theory_prompt["user"],
            step="Extrapolation",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_theory",
        )

        audit_prompt = get_theory_auditor_prompt(speculation)

        audit_result, _ = await run_agent(
            agent_name="Theoretical Auditor",
            system_prompt=audit_prompt["system"],
            user_prompt=audit_prompt["user"],
            step="Theory Audit",
            run_id=run_id,
            tools_names=[],
            submit_tool_name="submit_audit",
        )

        is_verified = audit_result.strip().upper().startswith("VERIFIED")
        if not is_verified:
            exec_service.log_transition(
                run_id,
                "Theoretical Auditor",
                f"Rejected theory for {universe.name}",
                "REVISION_REQUIRED",
                {"audit": audit_result},
            )
            continue

        theory_service.upsert_theory(universe.id, speculation, audit_result)

        generated_theories.append(
            {
                "universe_name": universe.name,
                "theory": speculation,
                "feedback": audit_result,
            }
        )

    exec_service.log_transition(
        run_id,
        "Ontological Theorist",
        "Completed interaction theories generation successfully",
        "COMPLETED",
        state,
    )

    return {"generated_theories": generated_theories, "active_task": "FINISHED"}
