"""
Full-stack browser-based UI smoke tests using cloakbrowser (Playwright wrapper).

These tests start a real uvicorn server subprocess sharing the ephemeral test
databases from conftest.py, then use BrowserManager to navigate pages, click
buttons, and verify the UI renders correctly.

Run with:  pytest tests/ui/test_e2e_browser.py -xvs
Skipped if cloakbrowser or playwright import fails.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("cloakbrowser")
pytest.importorskip("playwright")

# All async fixtures/tests in this module share one event loop so that
# BrowserManager's browser processes stay alive across test functions.
pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_PORT = int(os.getenv("E2E_PORT", "9877"))
BASE_URL = f"http://127.0.0.1:{BASE_PORT}"
POLL_INTERVAL = 0.3
MAX_POLLS = 40

# ── Session-scoped server subprocess ──────────────────────────────

_VERBOSE = os.getenv("E2E_VERBOSE", "")


@pytest.fixture(scope="session")
def server_url(seed_providers):
    """Start uvicorn as a subprocess sharing the test DB, yield URL, tear down.

    Explicitly depends on ``seed_providers`` so that the test databases are
    fully seeded *before* the server starts.  The subprocess inherits env vars
    (``DATABASE_URL`` etc.) set by ``conftest.py`` module-level code.

    All stderr output is captured and asserted empty after the session ends.
    """
    backend_dir = Path(__file__).resolve().parents[2]
    assert (backend_dir / "app" / "main.py").exists()

    env = os.environ.copy()
    env["BROWSER_POOL_SIZE"] = "1"
    env["BROWSER_MAX_CONCURRENCY_PER_INSTANCE"] = "2"

    captured_stderr: list[str] = []
    stderr_lock = threading.Lock()

    def _drain_stderr(stream):
        for line in iter(stream.readline, ""):
            with stderr_lock:
                captured_stderr.append(line)

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1",
            "--port", str(BASE_PORT),
            "--log-level", "error",
        ],
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Drain stderr on a background thread so the pipe buffer never blocks
    drainer = threading.Thread(
        target=_drain_stderr, args=(proc.stderr,), daemon=True
    )
    drainer.start()

    try:
        for _ in range(MAX_POLLS):
            try:
                import requests

                r = requests.get(f"{BASE_URL}/api/health", timeout=2)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)
        else:
            _print_captured_stderr(captured_stderr)
            pytest.fail(
                f"Server did not start within "
                f"{MAX_POLLS * POLL_INTERVAL:.0f}s on port {BASE_PORT}"
            )

        yield BASE_URL
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)

        drainer.join(timeout=2)

        # Collect remaining stderr after drainer finishes
        if proc.stderr and proc.stderr.readable():
            remaining = proc.stderr.read()
            if remaining:
                with stderr_lock:
                    captured_stderr.append(remaining)

        errors = [l for l in captured_stderr if _is_error_line(l)]
        if errors:
            header = f"Server stderr contained {len(errors)} error line(s):"
            joined = "\n".join(e.rstrip("\n") for e in errors)
            if _VERBOSE:
                all_lines = "".join(captured_stderr)
                print(f"\n--- all server stderr ({len(captured_stderr)} lines) ---\n{all_lines}")
            pytest.fail(f"{header}\n{joined}")


def _is_error_line(line: str) -> bool:
    lower = line.lower()
    if "error" in lower and "trace" in lower:
        return True
    if "traceback" in lower:
        return True
    if "critical" in lower:
        return True
    if "exception" in lower and "occurred" in lower:
        return True
    return False


def _print_captured_stderr(lines: list[str]):
    if lines:
        print("\n--- captured server stderr ---\n", "".join(lines), file=sys.stderr)


# ── Async browser fixture with console-error tracking ─────────────

_IGNORED_CONSOLE_PATTERNS = (
    "favicon.ico",
    "favicon",
    "data:image",
    "blob:",
    "About to navigate",
    "Application routes configured:",
    "Using menu routes:",
    "htmx.org",
)


def _is_ignored_console(text: str) -> bool:
    lower = text.lower()
    return any(p.lower() in lower for p in _IGNORED_CONSOLE_PATTERNS)


@pytest.fixture(scope="function")
async def browser_page():
    """Yield a Playwright Page with console-error & page-error listeners attached.

    After the test finishes, asserts that no ``console.error()``, failed
    ``console.assert()``, or unhandled JS exceptions occurred.
    """
    from app.core.browser import browser_manager

    async with browser_manager.page() as page:
        console_errors: list[str] = []
        page_errors: list[str] = []

        def on_console(msg):
            if msg.type in ("error", "assert"):
                text = f"[{msg.type}] {msg.text}"
                if not _is_ignored_console(text):
                    console_errors.append(text)

        def on_pageerror(err):
            page_errors.append(str(err))

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

        yield page

        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_pageerror)

        all_errors = console_errors + page_errors
        assert not all_errors, (
            f"Browser console/page errors detected:\n" + "\n".join(all_errors)
        )


# ── Helpers ───────────────────────────────────────────────────────

async def text(page) -> str:
    return await page.inner_text("body")


async def assert_contains(page, fragment: str, msg: str = ""):
    body = await text(page)
    assert fragment in body, msg or f"Expected {fragment!r} in page body"


async def sidebar_nav(page, label: str):
    el = page.locator("a", has_text=label).first
    await el.wait_for(timeout=5000)
    await el.click()
    await page.wait_for_load_state("networkidle")


# ── Tests ─────────────────────────────────────────────────────────

class TestPageLoads:
    """Every main page returns 200 and renders its shell."""

    @pytest.mark.parametrize("path,expect", [
        ("/research",    "Research"),
        ("/knowledge",   "Knowledge"),
        ("/logs",        "Execution"),
        ("/settings",    "Settings"),
        ("/theory",      "Theory"),
        ("/flow",        "Flow"),
        ("/validation",  "Validation"),
    ])
    async def test_page_loads(self, server_url, browser_page, path, expect):
        await browser_page.goto(f"{server_url}{path}", wait_until="networkidle")
        await assert_contains(browser_page, expect)


class TestSidebarNavigation:
    """Sidebar links navigate to the correct pages."""

    async def test_navigate_all_links(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/research", wait_until="networkidle")

        for label, expected_text in [
            ("Research",    "Focus"),
            ("Knowledge",   "Worlds"),
            ("Logs",        "Filter runs"),
            ("Settings",    "General"),
            ("Theory",      "Theories"),
            ("Validation",  "Validation"),
        ]:
            await sidebar_nav(browser_page, label)
            await assert_contains(browser_page, expected_text,
                f"after clicking sidebar {label!r}")


class TestResearchPage:
    """World table, search input, filter popup, Add World modal."""

    async def test_world_table_renders(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/research", wait_until="networkidle")
        await assert_contains(browser_page, "World Name")
        await assert_contains(browser_page, "Explore")

    async def test_search_input_present(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/research", wait_until="networkidle")
        search = browser_page.locator("input[name='q']")
        await search.wait_for(timeout=5000)
        current = await search.input_value()
        assert current is not None

    async def test_filter_popup_opens(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/research", wait_until="networkidle")
        btn = browser_page.locator("button", has_text="Filter").first
        await btn.wait_for(timeout=5000)
        await btn.click()
        await browser_page.wait_for_timeout(500)
        await assert_contains(browser_page, "Query Builder")

    async def test_add_world_modal_opens(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/research", wait_until="networkidle")
        btn = browser_page.locator("button", has_text="Add World").first
        await btn.wait_for(timeout=5000)
        await btn.click()
        await browser_page.wait_for_timeout(500)


class TestKnowledgePage:
    """Two-phase flow: world list → world detail with sub-tabs."""

    async def test_world_list_loads(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        await assert_contains(browser_page, "Worlds")

    async def test_world_detail_has_tabs(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        row = browser_page.locator("[onclick*='loadWorldDetail']").first
        if await row.count() == 0:
            pytest.skip("No worlds in database")

        await row.wait_for(timeout=8000)
        await row.click()
        await browser_page.wait_for_load_state("networkidle")

        await assert_contains(browser_page, "Back to worlds")
        await assert_contains(browser_page, "Overview")
        await assert_contains(browser_page, "Artifacts")
        await assert_contains(browser_page, "Notebook")
        await assert_contains(browser_page, "Theory")

    async def test_back_button_returns_to_list(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        row = browser_page.locator("[onclick*='loadWorldDetail']").first
        if await row.count() == 0:
            pytest.skip("No worlds in database")
        await row.wait_for(timeout=8000)
        await row.click()
        await browser_page.wait_for_load_state("networkidle")

        back = browser_page.locator("button", has_text="Back to worlds").first
        if await back.count() == 0:
            pytest.skip("Back button not found")
        await back.click()
        await browser_page.wait_for_load_state("networkidle")
        assert "world_id" not in browser_page.url

    async def test_focused_research_button(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/knowledge", wait_until="networkidle")
        row = browser_page.locator("[onclick*='loadWorldDetail']").first
        if await row.count() == 0:
            pytest.skip("No worlds in database")
        await row.wait_for(timeout=8000)
        await row.click()
        await browser_page.wait_for_load_state("networkidle")

        btn = browser_page.locator("button", has_text="Focused Research").first
        if await btn.count() == 0:
            pytest.skip("Focused Research button not found")
        await btn.click()
        await browser_page.wait_for_timeout(600)


class TestExecutionPage:
    """Run table and toolbar elements."""

    async def test_page_renders(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/logs", wait_until="networkidle")
        await browser_page.wait_for_timeout(1000)
        await assert_contains(browser_page, "View All Logs")
        await assert_contains(browser_page, "Abort All")

    async def test_filter_popup_opens(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/logs", wait_until="networkidle")
        btn = browser_page.locator("button", has_text="Filter").first
        if await btn.count() == 0:
            pytest.skip("Filter button not found")
        await btn.click()
        await browser_page.wait_for_timeout(500)
        await assert_contains(browser_page, "Query Builder")


class TestSettingsPage:
    """Tab switching and provider inspector."""

    async def test_tab_switching(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/settings", wait_until="networkidle")
        await browser_page.wait_for_timeout(500)

        for tab in ("General", "Providers", "Routes", "Health"):
            tab_btn = browser_page.locator("a, button", has_text=tab).first
            if await tab_btn.count() == 0:
                continue
            await tab_btn.click()
            await browser_page.wait_for_timeout(500)

    async def test_providers_tab_loads(self, server_url, browser_page):
        await browser_page.goto(f"{server_url}/settings", wait_until="networkidle")
        tab_btn = browser_page.locator("a, button", has_text="Providers").first
        if await tab_btn.count() == 0:
            pytest.skip("Providers tab not found")
        await tab_btn.click()
        await browser_page.wait_for_timeout(600)
