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

    # Create a universe in the notebook DB with a unique name
    import uuid
    uni_name = f"TestUni_{uuid.uuid4().hex[:6]}"
    from app.db.notebook_schema import NotebookUniverse
    from app.db.notebook_session import get_notebook_session
    with get_notebook_session() as session:
        u = NotebookUniverse(name=uni_name)
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
async def test_key_based_upsert_notebook_entry(_clean_db):
    service = WorkspaceService()
    universe_uuid = "uni-key"

    # 1. Create initial version by key
    e1 = service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        key="hypothesis-1",
        title="Initial Title",
        summary="Initial Summary",
        kind="Hypothesis",
        confidence=0.5
    )
    assert e1.id is not None
    assert e1.key == "hypothesis-1"
    assert e1.version == 1
    assert e1.confidence == 0.5

    # 2. Upsert same key - should create version 2
    e2 = service.upsert_notebook_entry(
        universe_uuid=universe_uuid,
        key="hypothesis-1",
        title="Updated Title",
        summary="Updated Summary",
        kind="Hypothesis",
        confidence=0.8
    )
    assert e2.id != e1.id
    assert e2.key == "hypothesis-1"
    assert e2.version == 2
    assert e2.confidence == 0.8

    # 3. Retrieve latest version via get_notebook_entry
    latest = service.get_notebook_entry(key="hypothesis-1", universe_uuid=universe_uuid)
    assert latest.version == 2
    assert latest.title == "Updated Title"

    # 4. Search notebook
    results = service.search_notebook_entries(universe_uuid, query="Updated", kind="Hypothesis")
    assert len(results) == 1
    assert results[0].version == 2


@pytest.mark.asyncio
async def test_manage_source_strengths_weaknesses(_clean_db):
    service = WorkspaceService()
    universe_uuid = "uni-src"
    url = "https://wiki.com/lore"

    src = service.upsert_source(
        universe_uuid=universe_uuid,
        url=url,
        title="Lore Wiki",
        strengths="Comprehensive coverage of factions",
        weaknesses="Outdated lore for recent patches"
    )
    assert src.id is not None
    assert src.strengths == "Comprehensive coverage of factions"
    assert src.weaknesses == "Outdated lore for recent patches"

    # Update strengths/weaknesses via source_id
    updated = service.upsert_source(
        universe_uuid=universe_uuid,
        url=url,
        strengths="Updated strengths",
        source_id=src.id
    )
    assert updated.strengths == "Updated strengths"
    assert updated.weaknesses == "Outdated lore for recent patches"
