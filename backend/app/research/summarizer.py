import asyncio
from typing import Dict, Any
from app.core.agent_engine import run_agent
from app.core.context import set_current_universe
from app.agents.prompts import get_summary_prompt
from app.services.universe_service import UniverseService

async def summarize_universe(universe_id: int, run_id: str) -> str:
    uni_service = UniverseService()
    universe = uni_service.get_universe_by_id(universe_id)
    if not universe:
        return "Universe not found."

    set_current_universe(universe.name)
    
    traits = uni_service.repo.get_traits(universe_id)
    traits_text = "\n".join([f"- {t.name}: {t.value}" for t in traits])
    
    raw_data = universe.raw_data or "No structured data available."
    structured_context = f"Structured JSON:\n{raw_data}\n\nExtracted Traits:\n{traits_text}"
    
    prompt = get_summary_prompt(universe.name, structured_context)
    
    summary, _ = await run_agent(
        agent_name="Universe Chronicler",
        system_prompt=prompt["system"],
        user_prompt=prompt["user"],
        step="Summarization",
        run_id=run_id,
        tools_names=[],
        submit_tool_name="submit_summary"
    )
    
    uni_service.update_summary(universe_id, summary)
    return summary
