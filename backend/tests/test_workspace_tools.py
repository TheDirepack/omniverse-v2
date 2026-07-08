import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.core.tools import (
    tool_load_notebook_entry,
    tool_save_notebook_entry,
    tool_manage_source,
    tool_record_timeline_event,
    tool_add_timeline_detail
)
from app.services.research_workspace import WorkspaceService
from app.db.unconfirmed_schema import NotebookEntry, ResearchSource, TimelineEntry

@pytest.mark.asyncio
async def test_tool_load_notebook_entry():
    with patch("app.services.research_workspace.WorkspaceService.get_notebook_entry") as mock_get:
        mock_get.return_value = NotebookEntry(
            id=1, title="Test", summary="Sum", kind="Lead", details="Det", status="OPEN", priority=1
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
         patch("app.services.research_workspace.WorkspaceService.upsert_notebook_entry") as mock_upsert:
        
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
         patch("app.services.research_workspace.WorkspaceService.upsert_source") as mock_upsert:
        
        mock_upsert.return_value = ResearchSource(id=1, url="http://test.com")
        
        res = await tool_manage_source({
            "url": "http://test.com",
            "title": "Test Source"
        })
        assert "updated/saved" in res
        mock_upsert.assert_called_once()

@pytest.mark.asyncio
async def test_tool_record_timeline_event():
    with patch("app.core.tools._get_universe_uuid", return_value="test-uuid"), \
         patch("app.services.research_workspace.WorkspaceService.create_timeline_event") as mock_create:
        
        mock_create.return_value = TimelineEntry(id=1, title="Event")
        
        res = await tool_record_timeline_event({
            "title": "Big Bang",
            "date": "T=0"
        })
        assert "recorded" in res
        mock_create.assert_called_once()

@pytest.mark.asyncio
async def test_tool_add_timeline_detail():
    with patch("app.services.research_workspace.WorkspaceService.add_timeline_participant") as mock_part, \
         patch("app.services.research_workspace.WorkspaceService.add_timeline_location") as mock_loc:
        
        res = await tool_add_timeline_detail({
            "timeline_id": 1,
            "type": "participant",
            "value_id": 10,
            "role": "Leader"
        })
        assert "Added participant" in res
        mock_part.assert_called_once_with(1, 10, "Leader")
        
        res = await tool_add_timeline_detail({
            "timeline_id": 1,
            "type": "location",
            "value_id": 20
        })
        assert "Added location" in res
        mock_loc.assert_called_once_with(1, 20)
