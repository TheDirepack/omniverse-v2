

class TestIndexPage:
    def test_index_page_returns_html(self, api_client):
        r = api_client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
