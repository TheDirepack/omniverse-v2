from unittest.mock import patch

import pytest

from app.core.tools import (
    tool_load_notebook_entry,
    tool_search_notebook,
    tool_manage_source,
    tool_save_notebook_entry,
    tool_expand_knowledge_node,
)
from app.db.notebook_schema import NotebookEntry, ResearchSource


@pytest.mark.asyncio
async def test_tool_load_notebook_entry():
    with patch(
        "app.services.research_workspace.WorkspaceService.get_notebook_entry"
    ) as mock_get:
        mock_get.return_value = NotebookEntry(
            id=1,
            title="Test",
            summary="Sum",
            kind="Lead",
            details="Det",
            status="OPEN",
            priority=1
        )
        res = await tool_load_notebook_entry({"entry_id": 1})
        assert "Notebook Entry 1" in res
        assert "Test" in res
        assert "Sum" in res

        mock_get.return_value = None
        res = await tool_load_notebook_entry({"entry_id": 999})
        assert "not found" in res

@pytest.mark.asyncio
async def test_tool_save_notebook_entry():
    with patch("app.core.tools._get_universe_uuid", return_value="test-uuid"), \
         patch(
             "app.services.research_workspace.WorkspaceService.upsert_notebook_entry"
         ) as mock_upsert:

        mock_upsert.return_value = NotebookEntry(id=1, title="T", summary="S")

        res = await tool_save_notebook_entry({
            "title": "Test Title",
            "summary": "Test Summary",
            "kind": "Hypothesis"
        })
        assert "saved successfully" in res
        mock_upsert.assert_called_once()

@pytest.mark.asyncio
async def test_tool_search_notebook():
    with patch("app.core.tools._get_universe_uuid", return_value="test-uuid"), \
         patch(
             "app.services.research_workspace.WorkspaceService.search_notebook_entries"
         ) as mock_search:

        mock_search.return_value = [
            NotebookEntry(id=1, key="k1", version=1, title="T1", summary="S1", kind="Hypothesis", status="OPEN", priority=5)
        ]

        res = await tool_search_notebook({"query": "T1"})
        assert "SEARCH RESULTS" in res
        assert "T1" in res
        mock_search.assert_called_once()


@pytest.mark.asyncio
async def test_tool_expand_knowledge_node():
    with patch("app.core.tools._get_universe_uuid", return_value="test-uuid"), \
         patch("app.core.tools.get_current_universe", return_value="TestUniverse"), \
         patch("sqlmodel.Session.exec") as mock_exec, \
         patch("app.services.knowledge_retriever.KnowledgeRetrieverService.get_universe_knowledge_graph") as mock_graph:

        from app.db.schema import Universe
        mock_exec.return_value.first.return_value = Universe(id=1, name="TestUniverse")
        mock_graph.return_value = {
            "Hero": {
                "facts": [{"predicate": "is_a", "object": "Warrior", "support": 2, "reference": "ref1"}],
                "related_entities": ["Sword"]
            }
        }

        res = await tool_expand_knowledge_node({"node_name": "Hero"})
        assert "Knowledge Expansion for Node: Hero" in res
        assert "is_a: Warrior" in res
        assert "Related Entities: Sword" in res


