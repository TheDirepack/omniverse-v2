"""Deterministic, fully-offline tests over cached real reference data.

These tests never touch the network. They read stable provider snapshots that
were seeded (by ``--slow`` tests) and committed under
``backend/tests_v2/fixtures/``, so they act on real-looking data deterministically
and offline.

A missing reference fails fast with a clear message instead of silently
fetching, preserving the default suite's offline guarantee.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import cached_references as cref
import pytest


@pytest.mark.unit
def test_deterministic_wikipedia_search_from_cache(cached_reference) -> None:
    """Real search snapshot shape + stable invariants, zero network I/O."""
    payload = cached_reference["wikipedia", "search_fusion_engine"]
    results = payload["query"]["search"]
    assert isinstance(results, list) and len(results) >= 1
    titles = [item["title"] for item in results]
    assert "Fusion engine" in titles


@pytest.mark.unit
def test_deterministic_mediawiki_siteinfo(cached_reference) -> None:
    """Cached MediaWiki siteinfo reads like a real provider response."""
    payload = cached_reference["mediawiki", "siteinfo_general"]
    general = payload["query"]["general"]
    assert general["sitename"] == "MediaWiki"
    assert "generator" in general


@pytest.mark.unit
def test_missing_reference_fails_fast_without_network(cached_reference) -> None:
    """Requesting an uncached reference raises; it never triggers a fetch."""
    with pytest.raises(KeyError, match="no cached reference"):
        cached_reference["wikipedia", "definitely_not_cached_sample_xyz"]


@pytest.mark.unit
def test_fixtures_dir_is_not_gitignored(reference_cache) -> None:
    """The fixtures cache lives under tests_v2/fixtures and is tracked."""
    assert not _git_check_ignore(reference_cache.root), (
        "backend/tests_v2/fixtures must be committed, and is not ignored"
    )


@pytest.mark.unit
def test_reference_cache_is_file_backed_and_reloadable(reference_cache) -> None:
    """Blobs persist as JSON and a fresh cache instance re-reads them."""
    root = reference_cache.root / "wikipedia" / "search_fusion_engine.json"
    assert root.exists() and root.stat().st_size > 0
    fresh = cref.ReferenceCache(reference_cache.root)
    payload = fresh.get("wikipedia", "search_fusion_engine")
    assert len(payload["query"]["search"]) >= 1


def _git_check_ignore(path: Path) -> bool:
    """Return True if `path` is excluded by the repo's .gitignore."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", str(path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
