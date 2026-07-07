import pytest
from app.db.schema import Universe
from app.db.session import engine
from sqlmodel import Session, select


@pytest.mark.asyncio
async def test_pipeline_auto_registers_worlds(client):
    """
    Tests that run_pipeline_in_background registers worlds in the DB if they don't exist.
    """
    # We trigger the pipeline via the orchestrate endpoint
    test_worlds = ["NewWorldA", "NewWorldB"]

    # Action: Start orchestration with non-existent worlds
    response = client.post("/api/runs/orchestrate", json={"worlds": test_worlds})
    assert response.status_code == 200

    # Since the pipeline runs in background, we might need to wait a bit,
    # but the registration happens at the very start of the background task.
    # However, the background task is spawned via BackgroundTasks which runs AFTER the response.
    # In TestClient, BackgroundTasks are executed immediately.

    # Verification: check if worlds now exist in the DB
    with Session(engine) as session:
        worlds = session.exec(
            select(Universe).where(Universe.name.in_(test_worlds))
        ).all()
        assert len(worlds) == 2
        names = [w.name for w in worlds]
        assert "NewWorldA" in names
        assert "NewWorldB" in names
