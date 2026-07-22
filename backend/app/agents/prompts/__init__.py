from .researcher import get_researcher_prompt
from .critic import get_critic_prompt
from .synthesis import get_synthesis_prompt
from .tiering import (
    get_architect_prompt,
    get_rubric_amendment_prompt,
    get_stability_prompt,
)
from .theory import get_extrapolation_prompt, get_theory_auditor_prompt
from .chronicler import get_summary_prompt, get_db_agent_prompt

__all__ = [
    "get_researcher_prompt",
    "get_critic_prompt",
    "get_synthesis_prompt",
    "get_architect_prompt",
    "get_rubric_amendment_prompt",
    "get_stability_prompt",
    "get_extrapolation_prompt",
    "get_theory_auditor_prompt",
    "get_summary_prompt",
    "get_db_agent_prompt",
]
