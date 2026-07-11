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

    # Create a universe in the unconfirmed DB
    from app.db.unconfirmed_schema import UnconfirmedUniverse
    from app.db.unconfirmed_session import get_unconfirmed_session
    with get_unconfirmed_session() as session:
        u = UnconfirmedUniverse(name="TestUni")
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
async def test_workspace_timeline_events(_clean_db):
    service = WorkspaceService()
    universe_uuid = "uni-123"

    event = service.create_timeline_event(universe_uuid, "The Big Bang", date="0")
    assert event.id is not None

    service.add_timeline_participant(event.id, 101, role="Creator")
    service.add_timeline_location(event.id, 201)

    # Verify they exist in DB
    from app.db.unconfirmed_session import get_unconfirmed_session
    with get_unconfirmed_session() as session:
        from app.db.unconfirmed_schema import TimelineLocation, TimelineParticipant
        p = session.exec(
            select(TimelineParticipant).where(
                TimelineParticipant.timeline_id == event.id
            )
        ).first()
        location = session.exec(
            select(TimelineLocation).where(TimelineLocation.timeline_id == event.id)
        ).first()
        assert p is not None
        assert p.role == "Creator"
        assert location is not None

@pytest.mark.asyncio
async def test_workspace_indexing(_clean_db):
    service = WorkspaceService()
    universe_uuid = "uni-idx"

    # Setup: Notebook, Source, Timeline
    service.upsert_notebook_entry(universe_uuid, "Note A", "Sum A", priority=10)
    service.upsert_source(
        universe_uuid, "http://src.com", title="Src A", reliability="High"
    )
    service.create_timeline_event(universe_uuid, "Event A", era="Era 1")

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

    # Test timeline index
    t_idx = service.get_timeline_index_str(universe_uuid)
    assert "TIMELINE EVENTS:" in t_idx
    assert "Event A" in t_idx
    assert "Era: Era 1" in t_idx

    # Test full index
    full_idx = service.get_full_workspace_index(universe_uuid)
    assert "RESEARCH NOTES:" in full_idx
    assert "USEFUL SOURCES:" in full_idx
    assert "TIMELINE EVENTS:" in full_idx
