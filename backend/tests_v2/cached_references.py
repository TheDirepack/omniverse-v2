"""Shared reference-fixture cache for tests_v2.

External network data is fetched at most once (typically by a ``--slow`` /
``--live`` test), stored as a stable reference blob under
``backend/tests_v2/fixtures/``, and reused verbatim by deterministic tests on
every run. Deterministic tests never trigger a live fetch: if the requested
reference is not already cached it is reported as missing rather than fetched,
keeping the default suite fully offline.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

CACHE_ROOT = Path(__file__).resolve().parent / "fixtures"

PROVIDER_DIRS: dict[str, str] = {
    "mediawiki": "mediawiki",
    "wikipedia": "wikipedia",
}

USER_AGENT = "omniverse-v2-tests/1.0 (+offline determinism; run --slow to refresh)"


def _safe_sample(sample: str) -> str:
    """Make a sample name filesystem-safe while staying human readable."""
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in sample)
    return safe or "reference"


def _http_get_json(url: str, *, timeout: float = 20.0) -> Mapping[str, Any]:
    """Fetch a JSON document over the network."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


class ReferenceCache:
    """File-backed cache of real provider responses keyed by (provider, sample)."""

    def __init__(
        self,
        root: Path = CACHE_ROOT,
        cache_hit_hook: Callable[[str], None] | None = None,
    ) -> None:
        self.root = root
        self.cache_hit_hook = cache_hit_hook

    # -- paths -------------------------------------------------------------
    def _paths(self, provider: str, sample: str) -> tuple[Path, Path, str]:
        dir_name = PROVIDER_DIRS.get(provider, provider)
        base = self.root / dir_name / _safe_sample(sample)
        return base.with_suffix(".json"), base.with_suffix(".meta.json"), base.name

    # -- introspection -----------------------------------------------------
    def has_reference(self, provider: str, sample: str) -> bool:
        data_path, _meta_path, _name = self._paths(provider, sample)
        return data_path.exists()

    def list_references(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            f"{p.parent.name}:{p.stem}"
            for p in self.root.rglob("*.json")
            if not p.name.endswith(".meta.json")
        )

    # -- read --------------------------------------------------------------
    def get(self, provider: str, sample: str) -> Mapping[str, Any]:
        """Return a cached reference blob. Never fetches over the network.

        Raises:
            KeyError: the reference is not present in the cache. Deterministic
                tests treat this as "run one --slow/--live test to seed the
                cache", never as a reason to go online.
        """
        data_path, _meta_path, _name = self._paths(provider, sample)
        if not data_path.exists():
            raise KeyError(
                f"no cached reference for ({provider!r}, {sample!r}); "
                "run a --slow/--live test to seed backend/tests_v2/fixtures/"
            )
        if self.cache_hit_hook:
            self.cache_hit_hook(f"{provider}:{sample}")
        with data_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    # -- write -------------------------------------------------------------
    def store(
        self,
        provider: str,
        sample: str,
        payload: Mapping[str, Any],
        *,
        source_url: str,
    ) -> Path:
        """Write a retrieved payload to the cache atomically. Idempotent."""
        data_path, meta_path, _name = self._paths(provider, sample)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        meta = {
            "provider": provider,
            "sample": sample,
            "source_url": source_url,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
            "note": "stable reference snapshot; refresh via a --slow/--live test",
        }
        _atomic_write_json(data_path, payload)
        _atomic_write_json(meta_path, meta)
        return data_path

    # -- fetch -------------------------------------------------------------
    def get_or_fetch(
        self,
        provider: str,
        sample: str,
        *,
        url: str,
        transform: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> Mapping[str, Any]:
        """Return the cached blob, or fetch + cache it on first use.

        Performs real network I/O only while the cache is empty; used by live
        (--slow / --live) tests only.
        """
        if self.has_reference(provider, sample):
            return self.get(provider, sample)
        payload = transform(_http_get_json(url)) if transform else _http_get_json(url)
        self.store(provider, sample, payload, source_url=url)
        return payload


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON atomically so a crashed writer never leaves partial data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    fd, tmp = tempfile.mkstemp(prefix=path.stem, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):  # pragma: no cover - best-effort cleanup
            os.unlink(tmp)
