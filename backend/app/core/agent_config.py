
AGENT_TOOLS = {
    "Researcher": [
        "webSearch",
        "fetchPage",
        "ocrImage",
        "saveNotebookEntry",
        "loadNotebookEntry",
        "deleteNotebookEntry",
        "modifyNotebookEntry",
    ],
    "LogicAuditor": [
        "fetchPage",
        "loadNotebookEntry",
        "queryArtifacts",
    ],
}

def get_tools_for_agent(agent_name: str) -> list[str]:
    return AGENT_TOOLS.get(agent_name, [])
