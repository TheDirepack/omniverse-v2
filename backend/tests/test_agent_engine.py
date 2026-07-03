import pytest
from app.core.agent_engine import FetchCache, run_fetch_cache


class TestFetchCache:
    def setup_method(self):
        run_fetch_cache.clear()

    def test_set_and_get(self):
        run_fetch_cache.set("http://example.com", "content here")
        assert run_fetch_cache.get("http://example.com") == "content here"

    def test_miss(self):
        assert run_fetch_cache.get("http://unknown.com") is None

    def test_overwrite(self):
        run_fetch_cache.set("http://x.com", "v1")
        run_fetch_cache.set("http://x.com", "v2")
        assert run_fetch_cache.get("http://x.com") == "v2"

    def test_clear(self):
        run_fetch_cache.set("http://a.com", "data")
        run_fetch_cache.clear()
        assert run_fetch_cache.get("http://a.com") is None

    def test_multiple_urls(self):
        run_fetch_cache.set("http://a.com", "a")
        run_fetch_cache.set("http://b.com", "b")
        assert run_fetch_cache.get("http://a.com") == "a"
        assert run_fetch_cache.get("http://b.com") == "b"

    def test_empty_url(self):
        run_fetch_cache.set("", "empty")
        assert run_fetch_cache.get("") == "empty"

    def test_none_key(self):
        with pytest.raises(TypeError):
            run_fetch_cache.set(None, "data")

    def test_none_value(self):
        run_fetch_cache.set("http://null.com", None)
        assert run_fetch_cache.get("http://null.com") is None

    def test_very_long_url(self):
        url = "http://x.com/" + "A" * 10000
        run_fetch_cache.set(url, "long url")
        assert run_fetch_cache.get(url) == "long url"

    def test_very_long_content(self):
        content = "A" * 1_000_000
        run_fetch_cache.set("http://big.com", content)
        assert len(run_fetch_cache.get("http://big.com")) == 1_000_000
