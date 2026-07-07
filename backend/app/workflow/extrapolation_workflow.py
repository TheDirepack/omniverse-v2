from typing import Any

from app.agents.prompts import get_extrapolation_prompt, get_theory_auditor_prompt
from app.core.agent_engine import run_agent
from app.core.context import set_current_universe
from app.services.execution_service import ExecutionService
from app.services.theory_service import TheoryService
from app.services.universe_service import UniverseService
from app.services.knowledge_retriever import KnowledgeRetrieverService


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
        "EXTRAPOLATING",
        state,
    )

    generated_theories = []

    verified_world_names = state.get("verified_worlds", [])
    universes = uni_service.get_by_names(verified_world_names)

    for universe in universes:
        if universe.id is None:
            continue
        set_current_universe(universe.name)

        retriever = KnowledgeRetrieverService()
        uni_context = retriever.get_claims_dataset(universe.id)

        comparison_texts = []
        for other in universes:
            if other.id == universe.id:
                continue
            other_dataset = retriever.get_claims_dataset(other.id)
            comparison_texts.append(f"World: {other.name}\nDataset:\n{other_dataset}")

        comparison_context = "\n\n---\n\n".join(comparison_texts)

        # Revision loop
        max_revisions = 3
        current_attempt = 0
        verified_theory = None
        final_audit = ""

        while current_attempt < max_revisions:
            theory_prompt = get_extrapolation_prompt(
                universe.name, uni_context, comparison_context
            )
            
            # If it's a revision, we need to tell the agent what was wrong
            user_prompt = theory_prompt["user"]
            if current_attempt > 0:
                user_prompt += f"\n\nPREVIOUS REJECTION FEEDBACK:\n{final_audit}"
        
            success, speculation, _ = await run_agent(
                agent_name="Ontological Theorist",
                system_prompt=theory_prompt["system"],
                user_prompt=user_prompt,
                step=f"Extrapolation (Attempt {current_attempt+1})",
                run_id=run_id,
                tools_names=[],
                submit_tool_name="submit_theory",
            )
        
            audit_prompt = get_theory_auditor_prompt(speculation)
            success_audit, audit_result, _ = await run_agent(
                agent_name="Theoretical Auditor",
                system_prompt=audit_prompt["system"],
                user_prompt=audit_prompt["user"],
                step=f"Theory Audit (Attempt {current_attempt+1})",
                run_id=run_id,
                tools_names=[],
                submit_tool_name="submit_audit",
            )
        
            if audit_result.strip().upper().startswith("VERIFIED"):
                verified_theory = speculation
                final_audit = audit_result
                break
            
            final_audit = audit_result
            current_attempt += 1


        if not verified_theory:
            exec_service.log_transition(
                run_id,
                "Theoretical Auditor",
                f"Discarded theory for {universe.name} after {max_revisions} failed revisions.",
                "REJECTED",
                {"last_audit": final_audit},
            )
            continue

        theory_service.upsert_theory(universe.id, verified_theory, final_audit)

        generated_theories.append(
            {
                "universe_name": universe.name,
                "theory": verified_theory,
                "feedback": final_audit,
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
