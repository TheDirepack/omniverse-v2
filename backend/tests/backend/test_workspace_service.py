import pytest
from sqlmodel import select

from app.services.research_workspace import WorkspaceService


@pytest.mark.asyncio
async def test_workspace_notebook_isolation(_clean_db):
    service = WorkspaceService()
    run_id_1 = "run-1"
    run_id_2 = "run-2"
    universe_uuid = "uni-123"

    # Save entry for run 1
    service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        title="Note 1",
        summary="Content 1",
        run_id=run_id_1
    )

    # Save entry for run 2
    service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        title="Note 1",
        summary="Content 2",
        run_id=run_id_2
    )

    # Verify isolation
    content_1 = service.get_notebook_content(run_id_1, universe_uuid)
    content_2 = service.get_notebook_content(run_id_2, universe_uuid)

    assert "Content 1" in content_1
    assert "Content 2" in content_2
    assert "Content 2" not in content_1
    assert "Content 1" not in content_2

@pytest.mark.asyncio
async def test_workspace_claim_isolation(_clean_db):
    service = WorkspaceService()
    run_id_1 = "run-1"
    run_id_2 = "run-2"

    # Create a universe in the notebook DB
    from app.db.notebook_schema import NotebookUniverse
    from app.db.notebook_session import get_notebook_session
    with get_notebook_session() as session:
        u = NotebookUniverse(name="TestUni")
        session.add(u)
        session.commit()
        session.refresh(u)
        universe_id = u.id

    claim_data = {"subject": "A", "predicate": "is", "object_val": "B"}

    service.upsert_workspace_claim(run_id_1, universe_id, claim_data)
    service.upsert_workspace_claim(run_id_2, universe_id, claim_data)

    kg_1 = service.get_working_kg(run_id_1, universe_id)
    kg_2 = service.get_working_kg(run_id_2, universe_id)

    assert len(kg_1) == 1
    assert len(kg_2) == 1

@pytest.mark.asyncio
async def test_workspace_source_management(_clean_db):
    service = WorkspaceService()
    universe_uuid = "uni-123"
    url = "https://wiki.com/page"

    source = service.upsert_source(universe_uuid, url, title="Title 1")
    assert source.id is not None
    assert source.title == "Title 1"

    # Update source
    updated = service.upsert_source(
        universe_uuid, url, title="Title 2", source_id=source.id
    )
    assert updated.id == source.id
    assert updated.title == "Title 2"



@pytest.mark.asyncio
async def test_workspace_indexing(_clean_db):
    service = WorkspaceService()
    universe_uuid = "uni-idx"

    # Setup: Notebook, Source
    service.upsert_notebook_entry(universe_uuid, "Note A", "Sum A", priority=10)
    service.upsert_source(
        universe_uuid, "http://src.com", title="Src A", reliability="High"
    )

    # Test notebook index
    n_idx = service.get_notebook_index_str(universe_uuid)
    assert "RESEARCH NOTES:" in n_idx
    assert "Note A" in n_idx
    assert "Priority: 10" in n_idx

    # Test source index
    s_idx = service.get_sources_index_str(universe_uuid)
    assert "USEFUL SOURCES:" in s_idx
    assert "Src A" in s_idx
    assert "Reliability: High" in s_idx

    # Test full index
    full_idx = service.get_full_workspace_index(universe_uuid)
    assert "RESEARCH NOTES:" in full_idx
    assert "USEFUL SOURCES:" in full_idx
