import pytest
from app.core.tools import AGENT_TOOLS

def test_unconfirmed_tools_removed():
    removed_tools = [
        "queryUnconfirmedClaims",
        "queryUnconfirmedArtifacts",
        "deleteUnconfirmedClaim",
        "deleteUnconfirmedArtifact"
    ]
    for tool in removed_tools:
        assert tool not in AGENT_TOOLS, f"Tool {tool} should have been removed from AGENT_TOOLS"

def test_notebook_tools_present():
    required_tools = [
        "saveNotebookEntry",
        "loadNotebookEntry",
        "deleteNotebookEntry"
    ]
    for tool in required_tools:
        assert tool in AGENT_TOOLS, f"Tool {tool} should be present in AGENT_TOOLS"
