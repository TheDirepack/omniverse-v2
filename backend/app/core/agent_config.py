
AGENT_TOOLS = {
    "Researcher": [
        "webSearch",
        "fetchPage",
        "ocrImage",
        "compareSourceFreshness",
        "saveNotebookEntry",
        "loadNotebookEntry",
        "deleteNotebookEntry",
        "modifyNotebookEntry",
    ],
    "LogicAuditor": [
        "fetchPage",
        "compareSourceFreshness",
        "loadNotebookEntry",
        "queryArtifacts",
    ],
}

def get_tools_for_agent(agent_name: str) -> list[str]:
    return AGENT_TOOLS.get(agent_name, [])
