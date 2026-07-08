import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import engine
from app.db.unconfirmed_session import unconfirmed_engine
from sqlmodel import Session, select
from app.db.schema import Universe
from app.db.unconfirmed_schema import NotebookEntry, ResearchSource, TimelineEntry

client = TestClient(app)

def test_workspace_notebook_view():
    with Session(engine) as session:
        u = Universe(name="TestWorld")
        session.add(u)
        session.commit()
        session.refresh(u)
        u_uuid = u.uuid

    with Session(unconfirmed_engine) as session:
        entry = NotebookEntry(
            universe_uuid=u_uuid,
            title="My Note",
            summary="My Summary",
            kind="Observation"
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        entry_id = entry.id

    client.cookies.set("active_world_id", u_uuid)
    
    # Test index page
    response = client.get("/research/workspace/notebook")
    assert response.status_code == 200
    assert "My Note" in response.text
    assert "My Summary" in response.text
    
    # Test detail page
    response = client.get(f"/research/workspace/notebook/{entry_id}")
    assert response.status_code == 200
    assert "My Note" in response.text
    assert "My Summary" in response.text

def test_workspace_sources_view():
    with Session(engine) as session:
        u = Universe(name="SourceWorld")
        session.add(u)
        session.commit()
        session.refresh(u)
        u_uuid = u.uuid

    with Session(unconfirmed_engine) as session:
        source = ResearchSource(
            universe_uuid=u_uuid,
            url="https://example.com",
            title="Example Source"
        )
        session.add(source)
        session.commit()

    client.cookies.set("active_world_id", u_uuid)
    response = client.get("/research/workspace/sources")
    assert response.status_code == 200
    assert "Example Source" in response.text
    assert "https://example.com" in response.text

def test_workspace_timeline_view():
    with Session(engine) as session:
        u = Universe(name="TimeWorld")
        session.add(u)
        session.commit()
        session.refresh(u)
        u_uuid = u.uuid

    with Session(unconfirmed_engine) as session:
        event = TimelineEntry(
            universe_uuid=u_uuid,
            title="The Big Bang",
            date="T=0",
            summary="Start of everything"
        )
        session.add(event)
        session.commit()

    client.cookies.set("active_world_id", u_uuid)
    response = client.get("/research/workspace/timeline")
    assert response.status_code == 200
    assert "The Big Bang" in response.text
    assert "T=0" in response.text
