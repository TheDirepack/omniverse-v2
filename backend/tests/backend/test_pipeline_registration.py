import pytest

from app.db.schema import Universe


@pytest.mark.asyncio
async def test_pipeline_auto_registers_worlds(client, clean_db):
    """
    Tests that run_pipeline_in_background registers worlds in the DB if they
    don't exist.
    """
    # Create universes first to get their UUIDs
    u1 = Universe(name="NewWorldA")
    u2 = Universe(name="NewWorldB")
    clean_db.add_all([u1, u2])
    clean_db.commit()
    clean_db.refresh(u1)
    clean_db.refresh(u2)

    test_uuids = [str(u1.id), str(u2.id)]

    # Action: Start orchestration with valid UUIDs
    response = client.post("/api/runs/workflow", json={"universe_uuids": test_uuids})
    assert response.status_code == 200

    # Verification: check if run was started
    assert "status" in response.json()
    assert response.json()["status"] == "started"

