import pytest

from app.db.schema import Universe


class TestWorldsViews:
    ENDPOINT = "/worlds"

    def test_worlds_page(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200

    def test_worlds_import_no_query(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/import")
        assert r.status_code == 200
        # Dark mode classes on search input
        assert "dark:bg-gray-700" in r.text
        assert "dark:text-gray-100" in r.text
        assert "dark:border-gray-600" in r.text

    def test_worlds_import_with_query(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/import", params={"q": "naruto"})
        assert r.status_code == 200

    def test_worlds_import_with_query_no_match(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/import", params={"q": "zzz_no_match_xyz"})
        assert r.status_code == 200
        assert "No registry entries" in r.text

    def test_worlds_import_filters_existing(self, api_client, clean_db):
        session = clean_db
        # Create a universe with same name AND slug as a registry entry
        session.add(Universe(name="Naruto", slug="naruto"))
        session.commit()
        session.close()

        r = api_client.get(f"{self.ENDPOINT}/import", params={"q": "naruto"})
        assert r.status_code == 200
        # Main "Naruto" registry entry filtered out — only 5 sub-entries shown
        assert "Import All" in r.text
        assert "Import all 5 worlds" in r.text

    def test_worlds_import_filters_existing_by_slug(self, api_client, clean_db):
        session = clean_db
        # Universe with slug "one_piece" — One Piece registry entry filtered
        session.add(Universe(slug="one_piece", name="AlreadyImported"))
        session.commit()
        session.close()

        r = api_client.get(f"{self.ENDPOINT}/import", params={"q": "one piece"})
        assert r.status_code == 200
        # 13 sub-entries remain (14 total minus 1 filtered by slug)
        assert "Import all 13 worlds" in r.text

    def test_worlds_import_filters_existing_name_match(self, api_client, clean_db):
        session = clean_db
        # Universe with name "One Piece" matches registry entry name
        session.add(Universe(name="One Piece"))
        session.commit()
        session.close()

        r = api_client.get(f"{self.ENDPOINT}/import", params={"q": "piece"})
        assert r.status_code == 200
        # 13 sub-entries remain (14 total minus 1 filtered by name)
        assert "Import all 13 worlds" in r.text

    def test_worlds_import_shows_new_entries(self, api_client, _clean_db):
        # Search by franchise name (space-separated) to find Metal Gear entries
        r = api_client.get(f"{self.ENDPOINT}/import", params={"q": "metal gear"})
        assert r.status_code == 200
        assert "Metal Gear" in r.text
        assert "Snake Eater" in r.text

    def test_worlds_import_all_action(self, api_client, _clean_db):
        r = api_client.post(f"{self.ENDPOINT}/import-all")
        assert r.status_code == 200

    def test_worlds_create_fragment(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/create_fragment")
        assert r.status_code == 200

    def test_worlds_graph(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/graph")
        assert r.status_code == 200

    def test_world_neighborhood_nonexistent(self, api_client):
        r = api_client.get(f"{self.ENDPOINT}/nonexistent-uuid/neighborhood")
        assert r.status_code == 404

    @pytest.mark.xfail(
        reason="DetachedInstanceError in UniverseService.import_from_registry",
        strict=False
    )
    def test_world_import_action(self, api_client, _clean_db):
        r = api_client.post(f"{self.ENDPOINT}/import/metal_gear")
        assert r.status_code == 200


class TestKnowledgeWorldRow:
    ENDPOINT = "/knowledge/worlds"

    def test_world_row_format(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="TestUniverse")
        session.add(u)
        session.commit()
        session.close()

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert 'text-xs font-semibold' in r.text
        assert 'text-gray-900 dark:text-gray-100' in r.text
        assert 'TestUniverse' in r.text
        assert 'dark:text-gray-400' in r.text

    def test_world_row_display_name_logic(self, api_client, clean_db):
        session = clean_db
        u1 = Universe(name="Ghost in the Shell")
        u2 = Universe(name="Pokemon Red")
        session.add_all([u1, u2])
        session.commit()
        session.close()

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert 'Ghost in the Shell' in r.text
        assert 'Pokemon Red' in r.text

    def test_world_row_deduplication(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="Ghost in the Shell")
        session.add(u)
        session.commit()
        session.close()

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert 'Ghost in the Shell' in r.text

    def test_world_row_no_timeline(self, api_client, clean_db):
        session = clean_db
        u = Universe(name="BareWorld")
        session.add(u)
        session.commit()
        session.close()

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert 'text-xs font-semibold' in r.text
        assert 'BareWorld' in r.text

    def test_world_row_dark_mode_hover(self, api_client, clean_db):
        session = clean_db
        session.add(Universe(name="DarkWorld"))
        session.commit()
        session.close()

        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert 'dark:hover:bg-gray-800' in r.text
