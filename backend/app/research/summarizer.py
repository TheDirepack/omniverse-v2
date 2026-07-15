from app.agents.prompts import get_summary_prompt
from app.core.agent_engine import Capability, run_agent
from app.core.context import set_current_universe
from app.services.universe_service import UniverseService


async def summarize_universe(universe_id: int, run_id: str) -> str:
    uni_service = UniverseService()
    universe = uni_service.get_universe_by_id(universe_id)
    if not universe:
        return "Universe not found."

    set_current_universe(universe.name)

    # Retrieve verified claims as the source of truth
    claims = uni_service.get_verified_claims(universe_id)

    if not claims:
        structured_context = "No verified claims found for this universe."
    else:
        # Format claims into a readable Knowledge Graph representation
        # Example: Subject -> Predicate -> Object
        claims_list = []
        for c in claims:
            pred = c.relation_type or "unknown"
            obj = f"Artifact({c.to_artifact_id})"

            claims_list.append(f"Artifact({c.from_artifact_id}) -> {pred} -> {obj}")

        structured_context = "Verified Knowledge Graph:\n" + "\n".join(claims_list)

    prompt = get_summary_prompt(universe.name, structured_context)

    _success, summary, _ = await run_agent(
        agent_name="Universe Chronicler",
        system_prompt=prompt["system"],
        user_prompt=prompt["user"],
        step=f"Summarize {universe.name}",
        run_id=run_id,
        tools_names=[],
        submit_tool_name="submit_summary",
        required_capabilities={Capability.READ_MAIN_DB},
    )



    uni_service.update_summary(universe_id, summary)
    return summary
