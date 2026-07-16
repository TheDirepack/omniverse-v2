import pytest

from app.db.schema import Universe
from app.services.universe_service import UniverseService


@pytest.mark.asyncio
class TestDbIntegrationNodeMarkExploredBatch:
    async def test_get_by_names_then_update_batch_does_not_crash(self, ephemeral_db):
        ephemeral_db.add(Universe(name="battletech", is_explored=False))
        ephemeral_db.commit()

        uni_service = UniverseService()
        research_results = [{"name": "battletech"}]

        universes = uni_service.get_by_names([r["name"] for r in research_results])
        assert len(universes) == 1
        for u in universes:
            u.is_explored = True
        uni_service.update_batch(universes)

        fresh_svc = UniverseService()
        reloaded = fresh_svc.get_by_names(["battletech"])
        assert reloaded[0].is_explored is True

    async def test_summary_node_lookup_does_not_crash(self, ephemeral_db):
        ephemeral_db.add(Universe(name="halo", is_explored=True))
        ephemeral_db.commit()

        uni_service = UniverseService()
        universes = uni_service.get_by_names(["halo"])
        universe_ids = [u.id for u in universes]
        assert len(universe_ids) == 1
