from unittest.mock import patch

import pytest

from app.core.tools import (
    tool_load_notebook_entry,
    tool_manage_source,
    tool_save_notebook_entry,
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
async def test_tool_manage_source():
    with patch("app.core.tools._get_universe_uuid", return_value="test-uuid"), \
         patch(
             "app.services.research_workspace.WorkspaceService.upsert_source"
         ) as mock_upsert:

        mock_upsert.return_value = ResearchSource(id=1, url="http://test.com")

        res = await tool_manage_source({
            "url": "http://test.com",
            "title": "Test Source"
        })
        assert "updated/saved" in res
        mock_upsert.assert_called_once()


