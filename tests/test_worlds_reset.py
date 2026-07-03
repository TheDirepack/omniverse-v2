import pytest
from app.db.session import engine
from sqlmodel import Session
from app.db.schema import Universe


class TestWorldsResetExplored:
    ENDPOINT = "/api/worlds"

    def test_reset_explored_single_world(self, client):
        client.post(self.ENDPOINT, json={"world_name": "SingleReset", "auto_research": False})
        worlds = client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "SingleReset")

        with Session(engine) as session:
            db_world = session.get(Universe, world["id"])
            db_world.is_explored = True
            session.add(db_world)
            session.commit()

        r = client.post(f"{self.ENDPOINT}/{world['id']}/reset-explored")
        assert r.status_code == 200

        worlds = client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "SingleReset")
        assert world["is_explored"] is False

    def test_reset_all_explored_filters_and_clears_flag(self, client):
        client.post(self.ENDPOINT, json={"world_name": "FilterTest", "auto_research": False})
        worlds = client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "FilterTest")

        with Session(engine) as session:
            db_world = session.get(Universe, world["id"])
            db_world.is_explored = True
            session.add(db_world)
            session.commit()

        r = client.post(f"{self.ENDPOINT}/reset-all-explored")
        assert r.status_code == 200
        assert r.json()["count"] == 1

        worlds = client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "FilterTest")
        assert world["is_explored"] is False

        r = client.post(f"{self.ENDPOINT}/reset-all-explored")
        assert r.json()["count"] == 0
