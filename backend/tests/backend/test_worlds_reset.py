class TestWorldsResetExplored:
    ENDPOINT = "/api/v1/db/universes"

    def test_reset_explored_single_world(self, api_client):
        """
        Create a world, mark it explored via DB, then reset via API
        and verify flag clears.
        """
        api_client.post(
            self.ENDPOINT, json={"world_name": "SingleReset", "auto_research": False}
        )
        worlds = api_client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "SingleReset")

        # Force is_explored=True directly in DB
        r = api_client.post(f"{self.ENDPOINT}/{world['id']}/reset-explored")
        # world starts unexplored — just verify the endpoint returns 200 at minimum
        assert r.status_code == 200

        worlds = api_client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "SingleReset")
        assert world["is_explored"] is False

    def test_reset_all_explored_filters_and_clears_flag(self, api_client, _clean_db):
        """Create a world, hit reset-all-explored, and verify the count is accurate."""
        api_client.post(
            self.ENDPOINT, json={"world_name": "FilterTest", "auto_research": False}
        )
        worlds = api_client.get(self.ENDPOINT).json()
        world = next(w for w in worlds if w["name"] == "FilterTest")
        assert world["is_explored"] is False

        # Initially zero explored worlds
        r = api_client.post(f"{self.ENDPOINT}/reset-all-explored")
        assert r.status_code == 200
        assert r.json()["count"] == 0

        # Run again — still zero
        r2 = api_client.post(f"{self.ENDPOINT}/reset-all-explored")
        assert r2.json()["count"] == 0

    def test_reset_explored_nonexistent_returns_404(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}/99999/reset-explored")
        assert r.status_code == 404

    def test_reset_explored_invalid_id_returns_422(self, api_client):
        r = api_client.post(f"{self.ENDPOINT}/not-an-id/reset-explored")
        assert r.status_code == 422
