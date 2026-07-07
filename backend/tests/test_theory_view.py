import pytest


class TestTheoryPage:
    ENDPOINT = "/theory"

    def test_theory_page_returns_html(self, api_client):
        r = api_client.get(self.ENDPOINT)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_reevaluate_theory(self, api_client):
        r = api_client.post(self.ENDPOINT + "/reevaluate", data={"universe_id": 1})
        assert r.status_code == 200
        assert "Re-evaluation triggered" in r.text
