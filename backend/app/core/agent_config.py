from typing import Any

AGENT_TOOLS = {
    "Researcher": [
        "webSearch",
        "fetchPage",
        "ocrImage",
        "compareSourceFreshness",
        "queryClaims",
        "queryUnconfirmedClaims",
        "saveUnconfirmedClaim",
    ],
    "LogicAuditor": [
        "fetchPage",
        "compareSourceFreshness",
        "queryClaims",
        "queryUnconfirmedClaims",
    ],
}

def get_tools_for_agent(agent_name: str) -> list[str]:
    return AGENT_TOOLS.get(agent_name, [])
