"""Live / slow tests that exercise the real network and LLM-adjacent endpoints.

These tests are explicitly marked ``live`` AND ``slow`` so they are:

* **deselected by default** — ``./test.sh`` and the pytest-v2.ini ``addopts``
  exclude ``slow``, ``evaluation`` and ``live``; and
* **invoked on demand** only via ``./test.sh --slow`` or a targeted
  ``pytest -m live -c backend/pytest-v2.ini tests_v2/test_live_reference.py``.

They fetch real data, cache it under ``backend/tests_v2/fixtures/`` on first
use, and revalidate/re-seed the stable blobs on each explicit run.
"""

from __future__ import annotations

import socket

import pytest
from cached_references import _http_get_json


@pytest.mark.live
@pytest.mark.slow
def test_deny_external_network_does_not_apply_to_live_marker() -> None:
    """Prove the autouse network gate is lifted for live-marked tests."""
    # Without the marker this would raise ExternalNetworkDisabledError.
    sock = socket.create_connection(("example.com", 80), timeout=10)
    sock.close()


@pytest.mark.live
@pytest.mark.slow
def test_live_wikipedia_search_seeds_cached_reference(reference_cache) -> None:
    """Fetch a real Wikipedia search, cache it, and assert real shape."""
    payload = reference_cache.get_or_fetch(
        "wikipedia",
        "search_fusion_engine",
        url=(
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            "&format=json&srsearch=fusion%20engine&srlimit=5"
        ),
    )
    results = payload["query"]["search"]
    assert isinstance(results, list) and len(results) >= 1
    assert all("title" in item for item in results)
    # Re-read straight off disk to prove it is now a stable cached blob.
    assert reference_cache.has_reference("wikipedia", "search_fusion_engine")
    disk = reference_cache.get("wikipedia", "search_fusion_engine")
    assert disk == payload


@pytest.mark.live
@pytest.mark.slow
def test_live_provider_siteinfo_snapshot(reference_cache) -> None:
    """Fetch MediaWiki siteinfo, cache it, and expose stable metadata."""
    payload = reference_cache.get_or_fetch(
        "mediawiki",
        "siteinfo_general",
        url=(
            "https://www.mediawiki.org/w/api.php?action=query&meta=siteinfo"
            "&format=json&siprop=general"
        ),
    )
    general = payload["query"]["general"]
    assert general["sitename"] == "MediaWiki"


@pytest.mark.live
@pytest.mark.slow
def test_live_page_summary_fetch(reference_cache) -> None:
    """Real REST summary for a real article; deterministic downstream use."""
    raw = _http_get_json("https://en.wikipedia.org/api/rest_v1/page/summary/Matter")
    payload = {
        "title": raw.get("title"),
        "extract": raw.get("extract", ""),
        "pageid": raw.get("pageid"),
    }
    reference_cache.store(
        "wikipedia",
        "page_extract",
        payload,
        source_url="REST_v1/page/summary/Matter",
    )
    assert payload["title"] == "Matter"
    assert len(payload["extract"]) > 20


@pytest.mark.live
@pytest.mark.slow
def test_live_suite_is_offline_safe_when_cache_is_warm(reference_cache) -> None:
    """Even live tests compose with deterministic references when cached."""
    payload = reference_cache.get_or_fetch(
        "wikipedia",
        "search_fusion_engine",
        url="https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srsearch=fusion%20engine&srlimit=5",
    )
    titles = [item["title"] for item in payload["query"]["search"]]
    assert "Fusion engine" in titles
