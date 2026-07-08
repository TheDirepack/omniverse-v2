import pytest
from sqlmodel import Session
from app.db.unconfirmed_session import unconfirmed_engine
from app.db.unconfirmed_schema import (
    NotebookEntry, 
    ResearchSource, 
    TimelineEntry, 
    TimelineParticipant, 
    TimelineLocation, 
    TimelineSource, 
    TimelineClaim
)
from app.services.research_workspace import WorkspaceService

def test_notebook_operations():
    with Session(unconfirmed_engine) as session:
        service = WorkspaceService(session=session)
        u_uuid = "test-universe-uuid"
        
        # Create entry
        entry = service.upsert_notebook_entry(
            universe_uuid=u_uuid,
            title="Test Lead",
            summary="This is a test summary",
            kind="Lead",
            details="Detailed notes here",
            priority=5
        )
        assert entry.id is not None
        assert entry.title == "Test Lead"
        
        # Get index
        index = service.get_notebook_index(u_uuid)
        assert len(index) == 1
        assert index[0].title == "Test Lead"
        
        # Get entry
        fetched = service.get_notebook_entry(entry.id)
        assert fetched.id == entry.id
        assert fetched.summary == "This is a test summary"
        
        # Update entry
        updated = service.upsert_notebook_entry(
            universe_uuid=u_uuid,
            title="Updated Lead",
            summary="Updated summary",
            kind="Lead",
            entry_id=entry.id
        )
        assert updated.title == "Updated Lead"
        assert updated.summary == "Updated summary"

def test_source_operations():
    with Session(unconfirmed_engine) as session:
        service = WorkspaceService(session=session)
        u_uuid = "test-universe-uuid-sources"
        
        # Create source
        source = service.upsert_source(
            universe_uuid=u_uuid,
            url="https://example.com",
            title="Example Source",
            reason_saved="High value",
            extraction_status="PARTIAL"
        )
        assert source.id is not None
        
        # Get sources
        sources = service.get_sources(u_uuid)
        assert len(sources) == 1
        assert sources[0].url == "https://example.com"
        
        # Update source
        updated = service.upsert_source(
            universe_uuid=u_uuid,
            url="https://example.com",
            extraction_status="COMPLETE",
            source_id=source.id
        )
        assert updated.extraction_status == "COMPLETE"

def test_timeline_operations():
    with Session(unconfirmed_engine) as session:
        service = WorkspaceService(session=session)
        u_uuid = "test-universe-uuid-timeline"
        
        # Create event
        event = service.create_timeline_event(
            universe_uuid=u_uuid,
            title="The Great War",
            date="2100 CE",
            summary="A huge conflict",
            importance=10
        )
        assert event.id is not None
        
        # Get timeline
        timeline = service.get_timeline(u_uuid)
        assert len(timeline) == 1
        assert timeline[0].title == "The Great War"
        
        # Add participants/location/etc
        # We need a dummy entity id for this since we are using unconfirmed_engine
        # but the schema refers to entity.id (which is in main db).
        # In tests, we can just use an integer.
        service.add_timeline_participant(event.id, entity_id=1, role="Commander")
        service.add_timeline_location(event.id, location_id=2)
        
        # Create a source to link
        source = service.upsert_source(universe_uuid=u_uuid, url="http://ev.com")
        service.add_timeline_source(event.id, source.id)
        
        # Link a claim (dummy id)
        service.add_timeline_claim(event.id, claim_id=100)
        
        # Verify event still exists
        assert service.get_timeline(u_uuid)[0].id == event.id
