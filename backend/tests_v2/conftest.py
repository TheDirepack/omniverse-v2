from __future__ import annotations

import socket
from pathlib import Path

import pytest

# `live` marks tests that are explicitly allowed to open external connections.
# They are deselected by default (see pytest-v2.ini and test.sh) and must be
# run with a targeted `-m live`/`--slow`/`--evaluation` invocation.
LIVE_MARKERS = ("live", "slow", "evaluation")


class ExternalNetworkDisabledError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("external network is disabled in tests_v2")


@pytest.fixture(autouse=True)
def deny_external_network(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    # Allow live-fetching tests to reach the network, but only when declared.
    if any(marker.name in LIVE_MARKERS for marker in request.node.iter_markers()):
        return

    def blocked_connect(self: socket.socket, _address: object) -> None:
        if self.family != socket.AF_UNIX:
            raise ExternalNetworkDisabledError

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


@pytest.fixture(scope="session")
def reference_cache():
    """Session-scoped cache of stable, real provider reference blobs.

    Deterministic tests read from this cache only (never the network); live
    tests use :meth:`ReferenceCache.get_or_fetch` to seed and refresh it.
    """
    from cached_references import ReferenceCache

    return ReferenceCache()


@pytest.fixture(scope="session")
def cached_reference(reference_cache):
    """Mapping-style view exposing ``cached_reference["provider", "sample"]``."""
    return _CachedReferenceView(reference_cache)


class _CachedReferenceView:
    """Read-only mapping view over the on-disk reference cache."""

    def __init__(self, cache) -> None:
        self._cache = cache

    def __getitem__(self, key: tuple[str, str]):
        provider, sample = key
        return self._cache.get(provider, sample)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, tuple) or len(key) != 2:
            return False
        provider, sample = key
        return self._cache.has_reference(provider, sample)


@pytest.fixture
def isolated_paths(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "database": tmp_path / "data" / "omniverse.db",
        "blobs": tmp_path / "blobs",
        "credentials": tmp_path / "secrets" / "credentials.json",
    }
    paths["database"].parent.mkdir()
    paths["blobs"].mkdir()
    paths["credentials"].parent.mkdir()
    return paths
