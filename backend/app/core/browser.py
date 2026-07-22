import asyncio
import logging
import os
import time
import urllib.request
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cloakbrowser import launch_async

logger = logging.getLogger(__name__)

BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}


def intercept_route(route):
    request = route.request
    # 1. Block heavy non-text resources (optional/configurable)
    # if request.resource_type in BLOCKED_RESOURCE_TYPES:
    #     return route.abort()

    # 2. Block ad and tracking URL keywords efficiently
    url = request.url
    if any(domain in url for domain in BLOCKED_DOMAINS):
        return route.abort()

    return route.continue_()


# ============================================================================
# Adblocker: Load and cache blocked domains from Anudeep's blacklist
# ============================================================================
BLOCKED_DOMAINS: set[str] = set()
_CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "adservers.txt"
_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours


def _load_blocked_domains() -> set[str]:
    """Load blocked domains from local cache file or fetch from remote source."""
    domains: set[str] = set()
    
    # Try to load from local cache first
    if _CACHE_FILE.exists():
        try:
            mtime = _CACHE_FILE.stat().st_mtime
            if time.time() - mtime < _MAX_AGE_SECONDS:
                with _CACHE_FILE.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            # Take the last part as the domain (handles 0.0.0.0, 127.0.0.1 prefixes)
                            domains.add(parts[-1].lower())
                logger.info("Loaded %d blocked domains from local cache", len(domains))
                return domains
        except Exception as e:
            logger.debug("Failed to load blocked domains from cache: %s", e)
    
    # Fetch from remote source
    try:
        url = "https://raw.githubusercontent.com/anudeepND/blacklist/master/adservers.txt"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            lines = resp.read().decode("utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    domains.add(parts[-1].lower())
        
        # Write to cache file
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _CACHE_FILE.open("w", encoding="utf-8") as f:
            for d in sorted(domains):
                f.write(f"0.0.0.0 {d}\n")
        
        logger.info("Loaded and cached %d blocked domains from remote source", len(domains))
    except Exception as e:
        logger.warning("Failed to fetch adserver blacklist: %s", e)
    
    return domains


# Load blocked domains on module import
BLOCKED_DOMAINS = _load_blocked_domains()

# Number of independent browser processes in the pool. Each process gets its
# own concurrency semaphore, so load spreads across real OS processes instead
# of all requests queuing behind a single cloakbrowser instance.
BROWSER_POOL_SIZE = int(os.getenv("BROWSER_POOL_SIZE", "2"))

# Max concurrent contexts per browser instance (mirrors the old global limit,
# but now scoped per-instance).
BROWSER_MAX_CONCURRENCY_PER_INSTANCE = int(
    os.getenv("BROWSER_MAX_CONCURRENCY_PER_INSTANCE", "5")
)


class _BrowserSlot:
    """One browser process + its own concurrency guard and load counter."""

    def __init__(self, index: int):
        self.index = index
        self.browser = None
        self.semaphore = asyncio.Semaphore(BROWSER_MAX_CONCURRENCY_PER_INSTANCE)
        self.active_contexts = 0
        self.lock = asyncio.Lock()  # guards launch/relaunch of this slot

    async def ensure_launched(self):
        if self.browser is not None:
            return
        async with self.lock:
            if self.browser is None:
                self.browser = await launch_async()

    async def relaunch(self):
        """Force a fresh browser process for this slot (used on crash detection)."""
        async with self.lock:
            if self.browser is not None:
                with suppress(Exception):
                    await self.browser.close()
            self.browser = await launch_async()

    async def close(self):
        async with self.lock:
            if self.browser is not None:
                with suppress(Exception):
                    await self.browser.close()
                self.browser = None


class BrowserManager:
    def __init__(self):
        self.pool: list[_BrowserSlot] = []
        # Track which slot a given context belongs to, so release_page() can
        # release the right semaphore/counter without changing the public
        # (page, context) return signature that callers already depend on.
        self._context_slot: dict[int, int] = {}
        self._context_slot_lock = asyncio.Lock()
        self._initialized = False
        self._initialize_pool(BROWSER_POOL_SIZE, BROWSER_MAX_CONCURRENCY_PER_INSTANCE)

    @property
    def browser(self):
        """Back-compat accessor: returns the first slot's browser handle
        (or None if not yet launched). Existing code/tests that only ever
        assumed a single browser can keep working against slot 0."""
        return self.pool[0].browser if self.pool else None

    async def start(self):
        # Browsers are launched lazily, on first get_page() call.
        return

    async def stop(self):
        for slot in self.pool:
            await slot.close()
        self.pool = []
        self._initialized = False

    def _initialize_pool(self, pool_size: int, max_concurrency: int):
        """Creates the browser pool based on provided configuration."""
        self.pool = [_BrowserSlot(i) for i in range(pool_size)]
        for slot in self.pool:
            slot.semaphore = asyncio.Semaphore(max_concurrency)
        self._initialized = True

    def _pick_least_loaded_slot(self) -> _BrowserSlot:
        return min(self.pool, key=lambda s: s.active_contexts)

    async def get_page(self):
        if not self._initialized:
            # Fallback lazy init if for some reason pool wasn't initialized.
            self._initialize_pool(
                BROWSER_POOL_SIZE, BROWSER_MAX_CONCURRENCY_PER_INSTANCE
            )

        slot = self._pick_least_loaded_slot()
        await slot.ensure_launched()

        await slot.semaphore.acquire()
        slot.active_contexts += 1
        context = None
        try:
            try:
                context = await slot.browser.new_context()
            except (TimeoutError, ConnectionError, OSError):
                # One retry: assume the process died, relaunch this slot only.
                logger.warning(
                    "Browser slot %d appears dead, relaunching", slot.index
                )
                await slot.relaunch()
                context = await slot.browser.new_context()

            page = await context.new_page()

            # Native Playwright Route Interception using optimized intercept_route
            if BLOCKED_DOMAINS:
                await page.route("**/*", intercept_route)

            async with self._context_slot_lock:
                self._context_slot[id(context)] = slot.index
            return page, context
        except Exception:
            logger.exception(
                "Failed to create browser page/context on slot %d", slot.index
            )
            if context:
                with suppress(Exception):
                    await context.close()
            slot.active_contexts -= 1
            slot.semaphore.release()
            raise

    async def update_config(self, pool_size: int, max_concurrency: int):
        """Updates pool size and concurrency, rebuilding the pool if necessary."""
        # Close existing browsers
        await self.stop()
        # Re-initialize with new config
        self._initialize_pool(pool_size, max_concurrency)
        logger.info(
            "Browser pool reconfigured: size=%d, concurrency=%d",
            pool_size,
            max_concurrency,
        )

    @asynccontextmanager
    async def page(self) -> AsyncGenerator[Any, None]:
        """
        Async context manager that provides a page and handles cleanup automatically.
        """
        page, context = await self.get_page()
        try:
            yield page
        finally:
            await page.close()
            await context.close()
            self.release_page(context)

    def release_page(self, context):
        # Look up (and forget) which slot this context belonged to. Falls
        # back to slot 0 if somehow untracked, to avoid a hard crash on
        # double-release or stale references.
        if not self.pool:
            return

        ctx_id = id(context)
        slot_index = self._context_slot.pop(ctx_id, None)
        slot = self.pool[slot_index] if slot_index is not None else self.pool[0]
        slot.active_contexts = max(0, slot.active_contexts - 1)
        slot.semaphore.release()
        # Note: caller is still responsible for closing the page and context.

    def pool_status(self) -> list[dict[str, Any]]:
        """Lightweight introspection for logging/metrics."""
        return [
            {
                "slot": s.index,
                "launched": s.browser is not None,
                "active_contexts": s.active_contexts,
            }
            for s in self.pool
        ]



browser_manager = BrowserManager()
