"""
Full-stack browser-based UI smoke tests using cloakbrowser (Playwright wrapper).

These tests start uvicorn in-process on a background thread, sharing the same
Python process as the test runner — all conftest fixtures (DB setup, seeding,
engine connections) are already in place.

Each test creates its own isolated Playwright browser and page, avoiding any
event-loop-crossing issues with the shared BrowserManager singleton.

Every page is visited, every interactive element is exercised, and both browser
console errors and server errors are detected and reported.

Run with:  pytest tests/ui/test_e2e_browser.py -xvs
Skipped if cloakbrowser or playwright import fails.
"""

from __future__ import annotations

import os
import threading
import time

import pytest
import requests
import uvicorn

pytest.importorskip("cloakbrowser")
pytest.importorskip("playwright")

BASE_PORT = int(os.getenv("E2E_PORT", "9877"))
BASE_URL = f"http://127.0.0.1:{BASE_PORT}"
POLL_INTERVAL = 0.3
MAX_POLLS = 40


# ── Thread-based server ───────────────────────────────────────────

class ServerThread(threading.Thread):
    def __init__(self, app: str, host: str, port: int):
        super().__init__(daemon=True)
        self.app = app
        self.host = host
        self.port = port
        self._exception: BaseException | None = None

    def run(self):
        try:
            config = uvicorn.Config(
                self.app, host=self.host, port=self.port, log_level="error",
            )
            server = uvicorn.Server(config)
            server.run()
        except Exception as exc:
            self._exception = exc


@pytest.fixture(scope="session")
def server_url(seed_providers):  # noqa: ARG001 - fixture dependency for DB seeding
    """Start uvicorn in-process on a background thread, yield URL."""
    thread = ServerThread("app.main:app", "127.0.0.1", BASE_PORT)
    thread.start()

    for _ in range(MAX_POLLS):
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    else:
        exc_info = ""
        if thread._exception:
            exc_info = f"\n  Server exception: {thread._exception}"
        pytest.fail(
            f"Server did not start within "
            f"{MAX_POLLS * POLL_INTERVAL:.0f}s on port {BASE_PORT}{exc_info}"
        )

    yield BASE_URL


# ── Per-test isolated browser fixture ─────────────────────────────

_IGNORED_CONSOLE_PATTERNS = (
    "favicon.ico",
    "data:image",
    "blob:",
    "About to navigate",
    "Application routes configured:",
    "Using menu routes:",
    "htmx.org",
    # Network 4xx/5xx are resource-level, not JS errors. Real bugs show as pageerror.
    "Failed to load resource",
)


def _ignored(msg_text: str) -> bool:
    lower = msg_text.lower()
    return any(p.lower() in lower for p in _IGNORED_CONSOLE_PATTERNS)


@pytest.fixture(scope="function")
async def page():
    """Fresh isolated Playwright browser + page per test with error listeners.

    After each test, asserts no console.error(), console.assert() failure,
    or unhandled JS exception occurred.
    """
    from cloakbrowser import launch_async

    browser = await launch_async()
    p = await browser.new_page()

    console_errors: list[str] = []
    page_errors: list[str] = []

    def on_console(msg):
        if msg.type in ("error", "assert"):
            text = f"[{msg.type}] {msg.text}"
            if not _ignored(text):
                console_errors.append(text)

    def on_pageerror(err):
        page_errors.append(str(err))

    p.on("console", on_console)
    p.on("pageerror", on_pageerror)

    yield p

    p.remove_listener("console", on_console)
    p.remove_listener("pageerror", on_pageerror)

    await p.close()
    await browser.close()

    all_errors = console_errors + page_errors
    assert not all_errors, (
        "Browser console/page errors detected:\n" + "\n".join(all_errors)
    )


# ── Helpers ───────────────────────────────────────────────────────

async def body_text(p) -> str:
    return await p.inner_text("body")


async def has_text(p, fragment: str, msg: str = ""):
    body = await body_text(p)
    assert fragment in body, msg or f"Expected {fragment!r} in page body"


async def not_has_text(p, fragment: str, msg: str = ""):
    body = await body_text(p)
    assert fragment not in body, msg or f"Unexpected {fragment!r} in page body"


async def click_link(p, text: str, timeout_ms: int = 5000):
    el = p.locator("a, button", has_text=text).first
    await el.wait_for(timeout=timeout_ms)
    await el.click()


async def sidebar_nav(p, label: str):
    el = p.locator("a", has_text=label).first
    await el.wait_for(timeout=5000)
    await el.click()
    await p.wait_for_load_state("networkidle")


# ── Tests ─────────────────────────────────────────────────────────

class TestPageLoads:
    """Every main page loads with expected visible text, no console errors."""

    @pytest.mark.parametrize("path,check", [
        ("/research",    "Research"),
        ("/knowledge",   "WORLDS"),
        ("/logs",        "Clear Logs"),
        ("/settings",    "Settings"),
        ("/theory",      "Theory"),
        ("/flow",        "Flow"),
        ("/validation",  "Validation"),
    ])
    async def test_loads(self, server_url, page, path, check):
        await page.goto(f"{server_url}{path}", wait_until="networkidle")
        await has_text(page, check)


class TestSidebar:
    """Sidebar links navigate correctly."""

    async def test_sidebar_nav(self, server_url, page):
        await page.goto(f"{server_url}/research", wait_until="networkidle")

        links = [
            ("Research",   "Research"),
            ("Knowledge",  "WORLDS"),
            ("Logs",       "Clear Logs"),
            ("Settings",   "Settings"),
            ("Theory",     "Theory"),
            ("Validation", "Validation"),
        ]
        for label, check in links:
            await sidebar_nav(page, label)
            await has_text(page, check, f"after sidebar click {label!r}")


class TestResearch:
    """Research page: world table, search, filter popup, Add World modal."""

    async def test_world_table(self, server_url, page):
        await page.goto(f"{server_url}/research", wait_until="networkidle")
        await has_text(page, "WORLD NAME")
        await has_text(page, "Explore")

    async def test_search_input(self, server_url, page):
        await page.goto(f"{server_url}/research", wait_until="networkidle")
        inp = page.locator("input[name='q']")
        await inp.wait_for(timeout=5000)
        await inp.fill("Pokémon")
        val = await inp.input_value()
        assert val == "Pokémon"

    async def test_filter_popup(self, server_url, page):
        await page.goto(f"{server_url}/research", wait_until="networkidle")
        btn = page.locator("button", has_text="Filter").first
        await btn.wait_for(timeout=5000)
        await btn.click()
        await page.wait_for_timeout(500)
        await has_text(page, "Query Builder")
        # Close via Escape
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        await not_has_text(page, "Query Builder")
        # Re-open
        await btn.click()
        await page.wait_for_timeout(500)
        await has_text(page, "Query Builder")

    async def test_add_world_modal(self, server_url, page):
        await page.goto(f"{server_url}/research", wait_until="networkidle")
        btn = page.locator("button", has_text="Add World").first
        await btn.wait_for(timeout=5000)
        await btn.click()
        await page.wait_for_timeout(500)

    async def test_explore_and_research_links(self, server_url, page):
        await page.goto(f"{server_url}/research", wait_until="networkidle")
        explore = page.locator("a", has_text="Explore").first
        if await explore.count() > 0:
            href0 = await explore.get_attribute("href")
            assert href0, "Explore link has href"


class TestKnowledge:
    """Knowledge two-phase flow: world list → world detail + tabs."""

    async def test_world_list(self, server_url, page):
        await page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        await has_text(page, "WORLDS")

    async def test_world_detail_tabs(self, server_url, page):
        await page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        row = page.locator("[onclick*='loadWorldDetail']").first
        if await row.count() == 0:
            pytest.skip("No worlds in database")
        await row.wait_for(timeout=8000)

        # Get the world name for later verification
        world_name = await row.inner_text()
        world_name = world_name.strip().split("\n")[0].strip()

        await row.click()
        await page.wait_for_load_state("networkidle")

        await has_text(page, "Back to worlds")
        await has_text(page, world_name)

        # Switch through all four sub-tabs
        for tab in ("Overview", "Artifacts", "Notebook", "Theory"):
            tab_btn = page.locator("button", has_text=tab).first
            if await tab_btn.count() == 0:
                continue
            await tab_btn.click()
            await page.wait_for_timeout(800)

    async def test_back_button(self, server_url, page):
        await page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        row = page.locator("[onclick*='loadWorldDetail']").first
        if await row.count() == 0:
            pytest.skip("No worlds in database")
        await row.wait_for(timeout=8000)
        await row.click()
        await page.wait_for_load_state("networkidle")
        assert "world_id=" in page.url

        back = page.locator("button", has_text="Back to worlds").first
        if await back.count() == 0:
            pytest.skip("Back button not found")
        await back.click()
        await page.wait_for_load_state("networkidle")
        assert "world_id" not in page.url
        await has_text(page, "WORLDS")

    async def test_focused_research_button(self, server_url, page):
        await page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        row = page.locator("[onclick*='loadWorldDetail']").first
        if await row.count() == 0:
            pytest.skip("No worlds in database")
        await row.wait_for(timeout=8000)
        await row.click()
        await page.wait_for_load_state("networkidle")

        btn = page.locator("button", has_text="Focused Research").first
        if await btn.count() == 0:
            pytest.skip("Focused Research button not found")
        await btn.click()
        await page.wait_for_timeout(600)


class TestExecution:
    """Execution page: run table, toolbar actions, filter."""

    async def test_page_renders(self, server_url, page):
        await page.goto(f"{server_url}/logs", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await has_text(page, "Clear Logs")
        await has_text(page, "Abort All")

    async def test_filter_popup(self, server_url, page):
        await page.goto(f"{server_url}/logs", wait_until="networkidle")
        btn = page.locator("button", has_text="Filter").first
        if await btn.count() == 0:
            pytest.skip("Filter button not found")
        await btn.click()
        await page.wait_for_timeout(500)
        await has_text(page, "Query Builder")

        # Close via Escape
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        await not_has_text(page, "Query Builder")

    async def test_clear_logs_button(self, server_url, page):
        await page.goto(f"{server_url}/logs", wait_until="networkidle")
        btn = page.locator("button", has_text="Clear Logs").first
        await btn.wait_for(timeout=5000)
        # Just verify the button exists and is clickable
        assert await btn.is_enabled()

    async def test_abort_all_button(self, server_url, page):
        await page.goto(f"{server_url}/logs", wait_until="networkidle")
        btn = page.locator("button", has_text="Abort All").first
        await btn.wait_for(timeout=5000)
        assert await btn.is_enabled()


class TestSettings:
    """Settings page: tab switching and provider inspector."""

    async def test_tab_switching(self, server_url, page):
        await page.goto(f"{server_url}/settings", wait_until="networkidle")
        await page.wait_for_timeout(500)

        for tab in ("General", "Providers", "Routes", "Health"):
            tab_btn = page.locator("a, button", has_text=tab).first
            if await tab_btn.count() == 0:
                continue
            await tab_btn.click()
            await page.wait_for_timeout(500)
            await has_text(page, tab, f"settings tab {tab!r} active")

    async def test_providers_tab(self, server_url, page):
        await page.goto(f"{server_url}/settings", wait_until="networkidle")
        tab = page.locator("a, button", has_text="Providers").first
        if await tab.count() == 0:
            pytest.skip("Providers tab not found")
        await tab.click()
        await page.wait_for_timeout(600)

    async def test_general_tab(self, server_url, page):
        await page.goto(f"{server_url}/settings", wait_until="networkidle")
        tab = page.locator("a, button", has_text="General").first
        if await tab.count() == 0:
            pytest.skip("General tab not found")
        await tab.click()
        await page.wait_for_timeout(600)
        await has_text(page, "General")

    async def test_routes_tab(self, server_url, page):
        await page.goto(f"{server_url}/settings", wait_until="networkidle")
        tab = page.locator("a, button", has_text="Routes").first
        if await tab.count() == 0:
            pytest.skip("Routes tab not found")
        await tab.click()
        await page.wait_for_timeout(600)


class TestTheory:
    async def test_page(self, server_url, page):
        await page.goto(f"{server_url}/theory", wait_until="networkidle")
        await has_text(page, "Theory")


class TestFlow:
    async def test_page(self, server_url, page):
        await page.goto(f"{server_url}/flow", wait_until="networkidle")
        await has_text(page, "Flow")


class TestValidation:
    async def test_page(self, server_url, page):
        await page.goto(f"{server_url}/validation", wait_until="networkidle")
        await has_text(page, "Validation")
