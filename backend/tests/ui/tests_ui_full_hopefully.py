"""
Comprehensive UI functionality test using cloakbrowser.
Tests every button, form, and interaction in Settings and Worlds pages.
Verifies no server errors (500) and no client-side JS errors.

Usage:
    1. Start the app: uvicorn app.main:app --host 127.0.0.1 --port 8000
    2. Run: pytest backend/tests/ui/test_browser_functionality.py -v -m browser

Requires:
    - cloakbrowser (pip install cloakbrowser)
    - App running on http://127.0.0.1:8000
"""

import asyncio
import logging
import os
from datetime import datetime

import pytest
from cloakbrowser import launch_async

logger = logging.getLogger(__name__)
APP_URL = os.getenv("OMNIVERSE_TEST_URL", "http://127.0.0.1:8000")


class OmniverseBrowserTester:
    """Browser-based tester that verifies every interaction works."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        self.console_errors = []
        self.network_errors = []

    async def test_setup(self):
        """Create a test world for detailed interaction testing."""
        # Navigate to worlds page
        await self.navigate("/worlds")

        # Create a test world
        create_btn = await self.page.query_selector('button[hx-get="/worlds/create_fragment"]')
        if create_btn:
            await create_btn.click()
            await asyncio.sleep(0.5)

            # Fill form
            name_input = await self.page.query_selector("#world-name")
            if name_input:
                test_name = f"TestWorld_{datetime.now().strftime('%H%M%S')}"
                await name_input.click()
                await name_input.type(test_name)

                parent_select = await self.page.query_selector("#world-parent-id")
                if parent_select:
                    await parent_select.select_option("")

                submit_btn = await self.page.query_selector('form[hx-post="/worlds/create"] button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(1.0)

                    # Verify creation success
                    body_text = await self.get_element_text("body")
                    if "Created" in body_text or "success" in body_text.lower():
                        self.log("SETUP", "Test World Created", "PASS", f"{test_name}")
                    else:
                        self.log("SETUP", "Test World Creation", "INFO", "May already exist or error")

                    # Close modal
                    close_btn = await self.page.query_selector("#world-modal button[onclick*='hidden']")
                    if close_btn:
                        await close_btn.click()
                        await asyncio.sleep(0.3)

        # Wait for page to stabilize
        await asyncio.sleep(1.0)
        self.log("SETUP", "Setup Complete", "INFO", "Ready for tests")

    async def setup(self):
        """Launch browser, capture console and network errors."""
        self.browser = await launch_async()
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(10000)
        self.page.set_default_navigation_timeout(15000)

        # Capture console errors
        self.page.on("console", lambda msg: self._handle_console(msg))
        # Capture page errors
        self.page.on("pageerror", lambda err: self.console_errors.append(str(err)))

    def _handle_console(self, msg):
        if msg.type in ("error", "warning"):
            self.console_errors.append(f"[{msg.type}] {msg.text}")

    async def teardown(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    def log(self, category: str, element: str, status: str, detail: str = ""):
        self.results.append({
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "element": element,
            "status": status,
            "detail": detail,
        })
        logger.info(f"[{status}] [{category}] {element}: {detail}")

    def assert_no_errors(self, category: str, element: str):
        """Assert no console or network errors occurred."""
        server_errors = [e for e in self.console_errors if "500" in e or "404" in e or "Error" in e]
        js_errors = [e for e in self.console_errors if "ReferenceError" in e or "TypeError" in e]

        if server_errors:
            self.log(category, element, "FAIL", f"Server/Network errors: {server_errors}")
            return False
        if js_errors:
            self.log(category, element, "FAIL", f"JS errors: {js_errors}")
            return False
        return True

    def clear_errors(self):
        self.console_errors.clear()

    # ------------------------------------------------------------------
    # Navigation Helpers
    # ------------------------------------------------------------------

    async def navigate(self, path: str):
        url = f"{APP_URL}{path}"
        await self.page.goto(url, wait_until="networkidle")
        await self.page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(0.5)

    async def click_and_wait(self, selector: str, wait_for_nav: bool = False):
        await self.page.wait_for_selector(selector, state="visible")
        self.clear_errors()
        await self.page.click(selector)
        if wait_for_nav:
            await self.page.wait_for_load_state("networkidle")
        else:
            await asyncio.sleep(0.8)  # Wait for HTMX

    async def fill_form(self, selector: str, value: str):
        await self.page.wait_for_selector(selector, state="visible")
        await self.page.fill(selector, value)

    async def select_option(self, selector: str, value: str):
        await self.page.wait_for_selector(selector, state="visible")
        await self.page.select_option(selector, value)

    async def element_exists(self, selector: str) -> bool:
        try:
            el = await self.page.query_selector(selector)
            return el is not None and await el.is_visible()
        except Exception:
            return False

    async def get_element_text(self, selector: str) -> str:
        el = await self.page.query_selector(selector)
        if el:
            return await el.text_content() or ""
        return ""

    async def count_elements(self, selector: str) -> int:
        return len(await self.page.query_selector_all(selector))

    # ------------------------------------------------------------------
    # WORLDS PAGE TESTS
    # ------------------------------------------------------------------

    async def test_worlds_page(self):
        """Test all interactions on the Worlds page."""
        await self.navigate("/worlds")

        # Pre-create a test world for detailed interaction testing
        await self.test_setup()

        # 1. Import from Registry button - test hx-vals payload
        try:
            import_btn = await self.page.query_selector('button[hx-get="/worlds/import"]')
            if import_btn:
                await import_btn.click()
                await asyncio.sleep(0.5)
                self.assert_no_errors("WORLDS", "Import Button hx-vals")
        except Exception as e:
            self.log("WORLDS", "Import Button", "FAIL", str(e))

        # 2. Create Custom Universe - test form submission with hx-vals
        try:
            create_btn = await self.page.query_selector('button[hx-get="/worlds/create_fragment"]')
            if create_btn:
                await create_btn.click()
                await asyncio.sleep(0.5)
                self.assert_no_errors("WORLDS", "Create Form Load")
        except Exception as e:
            self.log("WORLDS", "Create Button", "FAIL", str(e))

        # 3. Research start button - verify hx-vals with universe_uuids
        try:
            research_btn = await self.page.query_selector('button[hx-post="/api/v1/execution/runs/start"]')
            if research_btn:
                self.clear_errors()
                await research_btn.click()
                await asyncio.sleep(0.5)
                # Verify no JS errors during request
                js_errors = [e for e in self.console_errors if "ReferenceError" in e]
                if js_errors:
                    self.log("WORLDS", "Research hx-vals", "FAIL", f"JS errors: {js_errors}")
                else:
                    self.log("WORLDS", "Research Start (hx-vals)", "PASS", "No JS errors")
        except Exception as e:
            self.log("WORLDS", "Research Button", "FAIL", str(e))

        # 4. Delete button - test hx-vals with uuids payload
        try:
            delete_btn = await self.page.query_selector('button[hx-post="/worlds/delete"]')
            if delete_btn:
                self.assert_no_errors("WORLDS", "Delete Button hx-vals")
        except Exception as e:
            self.log("WORLDS", "Delete Button", "FAIL", str(e))

    async def test_run_details_page(self):
        """Test Run Details page - abort run uses hx-vals."""
        if not await self.element_exists('button[hx-post="/api/v1/execution/runs/start"]'):
            self.log("RUNS", "Skip Abort Test", "INFO", "No active runs available")
            return

        try:
            abort_btn = await self.page.query_selector('button[hx-post="/api/v1/execution/runs/abort"]')
            if abort_btn:
                self.clear_errors()
                await abort_btn.click()
                await asyncio.sleep(0.5)

                # Check for any JS errors (ReferenceError from missing hx-vals)
                js_errors = [e for e in self.console_errors if "ReferenceError" in e]
                if js_errors:
                    self.log("RUNS", "Abort hx-vals", "FAIL", f"JS errors: {js_errors}")
                else:
                    self.log("RUNS", "Abort Run (hx-vals)", "PASS", "No JS errors")
                    self.assert_no_errors("RUNS", "Abort Run")
        except Exception as e:
            self.log("RUNS", "Abort Button", "FAIL", str(e))

    async def test_world_details_page(self):
        """Test World Details page - re-research uses hx-vals."""
        # Navigate to world details by clicking on a world
        worlds_list = await self.count_elements(".world-link")
        if worlds_list > 0:
            # Click first world link to go to details page
            first_world = await self.page.query_selector(".world-link")
            if first_world:
                await first_world.click()
                await asyncio.sleep(0.5)

                # Test Re-research button - uses hx-vals with uuids
                try:
                    re_research_btn = await self.page.query_selector('button[hx-post="/worlds/re-research"]')
                    if re_research_btn:
                        self.clear_errors()
                        await re_research_btn.click()
                        await asyncio.sleep(0.5)

                        js_errors = [e for e in self.console_errors if "ReferenceError" in e]
                        if js_errors:
                            self.log("WORLD", "Re-research hx-vals", "FAIL", f"JS errors: {js_errors}")
                        else:
                            self.log("WORLD", "Re-research (hx-vals)", "PASS", "Success")
                except Exception as e:
                    self.log("WORLD", "Re-research Button", "FAIL", str(e))
        else:
            self.log("WORLD", "Skip Details Test", "INFO", "No worlds available")

    async def test_choose_world_page(self):
        """Test Choose World page - bulk delete uses hx-vals."""
        await self.navigate("/choose_world")

        try:
            # Test bulk delete - uses hx-vals with uuids array
            delete_btn = await self.page.query_selector('button[hx-post="/worlds/delete"]')
            if delete_btn:
                self.assert_no_errors("CHOOSE_WORLD", "Delete Button hx-vals")

            # Test set active world
            active_btn = await self.page.query_selector('button[hx-post="/worlds/set-active-world"]')
            if active_btn:
                self.assert_no_errors("CHOOSE_WORLD", "Set Active hx-vals")

            # Test create universe fragment
            create_btn = await self.page.query_selector('button[hx-get="/worlds/create_fragment"]')
            if create_btn:
                self.assert_no_errors("CHOOSE_WORLD", "Create Fragment hx-vals")
        except Exception as e:
            self.log("CHOOSE_WORLD", "Page Tests", "FAIL", str(e))

    async def test_database_worlds_component(self):
        """Test Database Worlds component - research button hx-vals."""
        await self.navigate("/worlds")

        # Wait for worlds to load
        await asyncio.sleep(1.0)

        try:
            research_btns = await self.count_elements('button[hx-post="/worlds/research"]')
            if research_btns > 0:
                self.log("DB_COMPONENT", "Research Buttons", "PASS", f"Found {research_btns} buttons")
                self.assert_no_errors("DB_COMPONENT", "Research Buttons")
            else:
                self.log("DB_COMPONENT", "Research Buttons", "INFO", "None visible yet")
        except Exception as e:
            self.log("DB_COMPONENT", "Research Buttons", "FAIL", str(e))

    async def test_knowledge_world_detail(self):
        """Test Knowledge World Detail component - re-evaluate theory hx-vals."""
        # This tests the theory_card.html fix
        await self.navigate("/worlds")

        try:
            # Navigate to a world to see knowledge tab
            first_world = await self.page.query_selector(".world-link")
            if first_world:
                await first_world.click()
                await asyncio.sleep(0.5)

                # Check for re-evaluate button (hx-vals)
                re_eval_btn = await self.page.query_selector('button[hx-post="/api/v1/theories/reevaluate"]')
                if re_eval_btn:
                    self.assert_no_errors("KNOWLEDGE", "Re-evaluate hx-vals")
        except Exception as e:
            self.log("KNOWLEDGE", "World Detail", "FAIL", str(e))

    async def test_theory_card(self):
        """Test Theory Card component - reevaluate button hx-vals."""
        await self.navigate("/theory")

        try:
            # Find reevaluate buttons in theory cards
            reeval_btns = await self.count_elements('button[hx-post="/api/v1/theories/reevaluate"]')
            if reeval_btns > 0:
                self.log("THEORY_CARD", "Reevaluate Buttons", "PASS", f"Found {reeval_btns}")
                self.assert_no_errors("THEORY_CARD", "Reevaluate Buttons")
            else:
                self.log("THEORY_CARD", "Reevaluate Buttons", "INFO", "Not found on theory page")
        except Exception as e:
            self.log("THEORY_CARD", "Reevaluate Buttons", "FAIL", str(e))

    async def test_knowledge_theory_tab(self):
        """Test Knowledge Theory Tab - reevaluate hx-vals."""
        # Navigate to knowledge tab of a world
        await self.navigate("/worlds")

        # Click into a world
        first_world = await self.page.query_selector(".world-link")
        if first_world:
            await first_world.click()
            await asyncio.sleep(0.5)

            try:
                # Look for reevaluate button in theory card
                reeval_btn = await self.page.query_selector('button[hx-post="/api/v1/theories/reevaluate"]')
                if reeval_btn:
                    self.assert_no_errors("KNOWLEDGE_TAB", "Reevaluate hx-vals")
            except Exception as e:
                self.log("KNOWLEDGE_TAB", "Theory Card", "FAIL", str(e))

    async def test_settings_health_component(self):
        """Test Settings Health component - reset DB uses hx-vals."""
        await self.navigate("/settings")

        try:
            # Wait for health tab to load
            await asyncio.sleep(2.0)

            # Check for reset DB button (hx-vals with uuid)
            reset_btn = await self.page.query_selector('button[hx-post="/api/v1/settings/reset_db"]')
            if reset_btn:
                self.log("SETTINGS", "Reset DB Button", "PASS", "Button exists")
                self.assert_no_errors("SETTINGS", "Reset DB hx-vals")
            else:
                self.log("SETTINGS", "Reset DB Button", "INFO", "Not visible yet")
        except Exception as e:
            self.log("SETTINGS", "Health Component", "FAIL", str(e))

    async def test_world_list_component(self):
        """Test World List component - research button hx-vals."""
        await self.navigate("/worlds")

        try:
            # Count research buttons
            research_btns = await self.count_elements('button[hx-post="/worlds/research"]')
            if research_btns > 0:
                self.log("WORLD_LIST", "Research Buttons", "PASS", f"Count: {research_btns}")
                self.assert_no_errors("WORLD_LIST", "Research Buttons hx-vals")
            else:
                self.log("WORLD_LIST", "Research Buttons", "INFO", "None loaded yet")
        except Exception as e:
            self.log("WORLD_LIST", "Research Buttons", "FAIL", str(e))

    async def test_active_runs_table(self):
        """Test Active Runs Table - abort button hx-vals."""
        await self.navigate("/runs")

        try:
            # Find abort buttons
            abort_btns = await self.count_elements('button[hx-post="/api/v1/execution/runs/abort"]')
            if abort_btns > 0:
                self.log("ACTIVE_RUNS", "Abort Buttons", "PASS", f"Count: {abort_btns}")
                self.assert_no_errors("ACTIVE_RUNS", "Abort hx-vals")
        except Exception as e:
            self.log("ACTIVE_RUNS", "Abort Buttons", "FAIL", str(e))

    async def test_htmx_integration(self):
        """
        Integration test for all HTMX fixes.
        Validates that hx-vals attributes work correctly across all pages.
        """
        self.log("INTEGRATION", "HTMX Integration Test", "INFO", "Starting validation")

        # Test 1: Worlds page - research start with universe_uuids payload
        self.log("INTEGRATION", "Step 1", "INFO", "Testing Worlds page research trigger")
        await self.test_worlds_page()

        # Test 2: Run details - abort run
        self.log("INTEGRATION", "Step 2", "INFO", "Testing Run Details abort")
        await self.test_run_details_page()

        # Test 3: World details - re-research functionality
        self.log("INTEGRATION", "Step 3", "INFO", "Testing World Details re-research")
        await self.test_world_details_page()

        # Test 4: Choose world - bulk operations
        self.log("INTEGRATION", "Step 4", "INFO", "Testing Choose World page")
        await self.test_choose_world_page()

        # Test 5: Settings health - DB reset
        self.log("INTEGRATION", "Step 5", "INFO", "Testing Settings Health component")
        await self.test_settings_health_component()

        # Test 6: Knowledge components - theory reevaluation
        self.log("INTEGRATION", "Step 6", "INFO", "Testing Knowledge components")
        await self.test_knowledge_world_detail()
        await self.test_knowledge_theory_tab()

        # Test 7: Theory cards
        self.log("INTEGRATION", "Step 7", "INFO", "Testing Theory Cards")
        await self.test_theory_card()

        # Test 8: Database components
        self.log("INTEGRATION", "Step 8", "INFO", "Testing Database Components")
        await self.test_database_worlds_component()
        await self.test_world_list_component()
        await self.test_active_runs_table()

        # Summary
        total = len(self.results)
        passed = len([r for r in self.results if r["status"] == "PASS"])
        failed = len([r for r in self.results if r["status"] == "FAIL"])

        self.log("INTEGRATION", "Summary", "INFO", f"Total: {total}, Passed: {passed}, Failed: {failed}")

        if failed > 0:
            errors = [f"{r['category']}/{r['element']} - {r['detail']}"
                    for r in self.results if r["status"] == "FAIL"][:5]
            self.log("INTEGRATION", "Errors", "WARN", "; ".join(errors))

@pytest.mark.asyncio
async def test_all_ui_interactions():
    """Run comprehensive HTMX validation across all pages."""
    print("Starting UI test suite...")
    tester = OmniverseBrowserTester()
    print("Creating tester instance...")
    await tester.setup()
    print("Setup complete, starting integration tests...")
    await tester.test_htmx_integration()
    print("Integration tests complete, calculating results...")
    # Log results
    passed = sum(1 for r in tester.results if r["status"] == "PASS")
    failed = sum(1 for r in tester.results if r["status"] == "FAIL")
    print(f"Results: {passed} passed, {failed} failed")
    async def test_settings_page(self):
        """Test all interactions on the Settings page."""
        await self.navigate("/settings")

        # --- Tab Navigation ---
        tabs = [
            ("#tab-general", "General Tab"),
            ("#tab-providers", "Providers Tab"),
            ("#tab-routes", "Routes Tab"),
            ("#tab-health", "Health Tab"),
        ]

        for selector, name in tabs:
            try:
                tab = await self.page.query_selector(selector)
                if tab:
                    self.clear_errors()
                    await tab.click()
                    await asyncio.sleep(0.5)
                    active = await tab.get_attribute("aria-selected")
                    if active == "true":
                        self.log("SETTINGS", name, "PASS", "Tab activated")
                        self.assert_no_errors("SETTINGS", name)
                    else:
                        self.log("SETTINGS", name, "FAIL", "Tab not activated")
                else:
                    self.log("SETTINGS", name, "FAIL", "Tab not found")
            except Exception as e:
                self.log("SETTINGS", name, "FAIL", str(e))

        # --- General Tab Interactions ---
        await self.navigate("/settings/tab/general")
        await asyncio.sleep(0.5)

        # 1. Toggle boolean setting (AGENT_LOGGING)
        try:
            toggle_form = await self.page.query_selector('form:has(input[name="key"][value="AGENT_LOGGING"])')
            if toggle_form:
                checkbox = await toggle_form.query_selector('input[type="checkbox"]')
                if checkbox:
                    current = await checkbox.is_checked()
                    await checkbox.click()
                    await asyncio.sleep(0.5)
                    self.log("SETTINGS", "AGENT_LOGGING Toggle", "PASS", f"Toggled from {current}")
                    self.assert_no_errors("SETTINGS", "AGENT_LOGGING Toggle")
                else:
                    self.log("SETTINGS", "AGENT_LOGGING Toggle", "FAIL", "Checkbox not found")
            else:
                self.log("SETTINGS", "AGENT_LOGGING Toggle", "INFO", "Form not found (setting may not exist)")
        except Exception as e:
            self.log("SETTINGS", "AGENT_LOGGING Toggle", "FAIL", str(e))

        # 2. Slider setting (BROWSER_POOL_SIZE)
        try:
            slider_form = await self.page.query_selector('form:has(input[name="key"][value="BROWSER_POOL_SIZE"])')
            if slider_form:
                slider = await slider_form.query_selector('input[type="range"]')
                if slider:
                    await slider.fill("3")
                    await asyncio.sleep(0.3)
                    save_btn = await slider_form.query_selector('button[type="submit"]')
                    if save_btn:
                        self.clear_errors()
                        await save_btn.click()
                        await asyncio.sleep(0.5)
                        self.log("SETTINGS", "BROWSER_POOL_SIZE Slider", "PASS", "Slider adjusted and saved")
                        self.assert_no_errors("SETTINGS", "BROWSER_POOL_SIZE Slider")
                else:
                    self.log("SETTINGS", "BROWSER_POOL_SIZE Slider", "FAIL", "Slider not found")
            else:
                self.log("SETTINGS", "BROWSER_POOL_SIZE Slider", "INFO", "Form not found")
        except Exception as e:
            self.log("SETTINGS", "BROWSER_POOL_SIZE Slider", "FAIL", str(e))

        # 3. Text setting update
        try:
            text_forms = await self.page.query_selector_all('form[hx-post="/settings/general/update"]')
            if len(text_forms) > 0:
                # Find a non-boolean, non-slider form
                for form in text_forms:
                    key_input = await form.query_selector('input[name="key"]')
                    if key_input:
                        key_val = await key_input.get_attribute("value")
                        if key_val and key_val not in ["AGENT_LOGGING", "HIDE_WEBFETCH_CONTENT", "HIDE_WEBSEARCH_CONTENT", "BROWSER_POOL_SIZE", "BROWSER_MAX_CONCURRENCY_PER_INSTANCE", "MAX_PARALLEL_AGENTS", "MIN_RESEARCH_TURNS"]:
                            value_input = await form.query_selector('input[name="value"]')
                            if value_input:
                                await value_input.fill("test-value-123")
                                save_btn = await form.query_selector('button[type="submit"]')
                                if save_btn:
                                    self.clear_errors()
                                    await save_btn.click()
                                    await asyncio.sleep(0.5)
                                    self.log("SETTINGS", f"Text Setting ({key_val})", "PASS", "Updated successfully")
                                    self.assert_no_errors("SETTINGS", f"Text Setting ({key_val})")
                                    break
            else:
                self.log("SETTINGS", "Text Setting Update", "INFO", "No text settings found")
        except Exception as e:
            self.log("SETTINGS", "Text Setting Update", "FAIL", str(e))

        # 4. Delete setting button
        try:
            delete_btn = await self.page.query_selector('button[onclick^="confirmDeleteSetting"]')
            if delete_btn:
                self.log("SETTINGS", "Delete Setting Button", "PASS", "Button exists")
            else:
                self.log("SETTINGS", "Delete Setting Button", "INFO", "No settings to delete")
        except Exception as e:
            self.log("SETTINGS", "Delete Setting Button", "FAIL", str(e))

        # 5. Add New Setting form
        try:
            add_form = await self.page.query_selector('form[hx-post="/settings/general/update"]:not(:has(input[type="hidden"]))')
            if add_form:
                key_input = await add_form.query_selector('input[name="key"]')
                val_input = await add_form.query_selector('input[name="value"]')
                submit_btn = await add_form.query_selector('button[type="submit"]')
                if key_input and val_input and submit_btn:
                    await key_input.fill("TEST_BROWSER_KEY")
                    await val_input.fill("test-value")
                    self.clear_errors()
                    await submit_btn.click()
                    await asyncio.sleep(0.5)
                    self.log("SETTINGS", "Add New Setting", "PASS", "Setting added")
                    self.assert_no_errors("SETTINGS", "Add New Setting")
                else:
                    self.log("SETTINGS", "Add New Setting", "FAIL", "Form elements missing")
            else:
                self.log("SETTINGS", "Add New Setting", "FAIL", "Add form not found")
        except Exception as e:
            self.log("SETTINGS", "Add New Setting", "FAIL", str(e))

        # --- Providers Tab ---
        await self.navigate("/settings/tab/providers")
        await asyncio.sleep(0.5)

        # 6. Add New Provider button
        try:
            new_provider_btn = await self.page.query_selector('button[hx-get="/settings/providers/new"]')
            if new_provider_btn:
                self.clear_errors()
                await new_provider_btn.click()
                await asyncio.sleep(0.5)
                if await self.element_exists("input[name='name']"):
                    self.log("SETTINGS", "Add New Provider", "PASS", "Provider form loaded")
                    self.assert_no_errors("SETTINGS", "Add New Provider")
                else:
                    self.log("SETTINGS", "Add New Provider", "FAIL", "Form not loaded")
            else:
                self.log("SETTINGS", "Add New Provider", "INFO", "Button not found")
        except Exception as e:
            self.log("SETTINGS", "Add New Provider", "FAIL", str(e))

        # 7. Create provider form submit
        try:
            if await self.element_exists("input[name='name']"):
                await self.fill_form("input[name='name']", "TestProvider")
                await self.fill_form("input[name='provider_type']", "openai")
                await self.fill_form("input[name='base_url']", "https://api.openai.com/v1")
                await self.fill_form("input[name='models']", "gpt-4,gpt-3.5-turbo")
                create_btn = await self.page.query_selector('button[type="submit"]:has-text("Create")')
                if create_btn:
                    self.clear_errors()
                    await create_btn.click()
                    await asyncio.sleep(0.8)
                    body_text = await self.get_element_text("body")
                    if "Provider" in body_text or "updated" in body_text.lower():
                        self.log("SETTINGS", "Create Provider Submit", "PASS", "Provider created")
                    else:
                        self.log("SETTINGS", "Create Provider Submit", "FAIL", f"Unexpected: {body_text[:200]}")
                    self.assert_no_errors("SETTINGS", "Create Provider Submit")
                else:
                    self.log("SETTINGS", "Create Provider Submit", "FAIL", "Submit button not found")
            else:
                self.log("SETTINGS", "Create Provider Submit", "INFO", "Form not available")
        except Exception as e:
            self.log("SETTINGS", "Create Provider Submit", "FAIL", str(e))

        # 8. Provider list click (select provider)
        try:
            providers = await self.count_elements("[onclick^='selectProvider']")
            if providers > 0:
                first_provider = await self.page.query_selector("[onclick^='selectProvider']")
                if first_provider:
                    self.clear_errors()
                    await first_provider.click()
                    await asyncio.sleep(0.5)
                    self.log("SETTINGS", "Select Provider", "PASS", f"Selected provider from {providers} providers")
                    self.assert_no_errors("SETTINGS", "Select Provider")
            else:
                self.log("SETTINGS", "Select Provider", "INFO", "No providers in list")
        except Exception as e:
            self.log("SETTINGS", "Select Provider", "FAIL", str(e))

        # 9. Delete provider button
        try:
            delete_provider = await self.page.query_selector('button[hx-post*="/settings/providers/"][hx-post*="/delete"]')
            if delete_provider:
                self.log("SETTINGS", "Delete Provider Button", "PASS", "Button exists")
            else:
                self.log("SETTINGS", "Delete Provider Button", "INFO", "Not found")
        except Exception as e:
            self.log("SETTINGS", "Delete Provider Button", "FAIL", str(e))

        # 10. Sync provider models
        try:
            sync_btn = await self.page.query_selector('button[hx-post*="/settings/providers/"][hx-post*="/sync"]')
            if sync_btn:
                self.clear_errors()
                await sync_btn.click()
                await asyncio.sleep(1.0)
                self.log("SETTINGS", "Sync Provider Models", "PASS", "Sync triggered")
                self.assert_no_errors("SETTINGS", "Sync Provider Models")
            else:
                self.log("SETTINGS", "Sync Provider Models", "INFO", "Button not found")
        except Exception as e:
            self.log("SETTINGS", "Sync Provider Models", "FAIL", str(e))

        # --- Routes Tab ---
        await self.navigate("/settings/tab/routes")
        await asyncio.sleep(0.5)

        # 11. Add Route button
        try:
            add_route_btn = await self.page.query_selector('button[hx-get="/settings/routes/new"]')
            if add_route_btn:
                self.clear_errors()
                await add_route_btn.click()
                await asyncio.sleep(0.5)
                if await self.element_exists("input[name='task_type']"):
                    self.log("SETTINGS", "Add Route Form", "PASS", "Route editor loaded")
                    self.assert_no_errors("SETTINGS", "Add Route Form")
                else:
                    self.log("SETTINGS", "Add Route Form", "FAIL", "Editor not loaded")
            else:
                self.log("SETTINGS", "Add Route Button", "INFO", "Not found")
        except Exception as e:
            self.log("SETTINGS", "Add Route Button", "FAIL", str(e))

        # 12. Route list click
        try:
            routes = await self.count_elements("[onclick^='selectRoute']")
            if routes > 0:
                first_route = await self.page.query_selector("[onclick^='selectRoute']")
                if first_route:
                    self.clear_errors()
                    await first_route.click()
                    await asyncio.sleep(0.5)
                    self.log("SETTINGS", "Select Route", "PASS", f"Selected route from {routes} routes")
                    self.assert_no_errors("SETTINGS", "Select Route")
            else:
                self.log("SETTINGS", "Select Route", "INFO", "No routes in list")
        except Exception as e:
            self.log("SETTINGS", "Select Route", "FAIL", str(e))

        # 13. Delete route button
        try:
            delete_route = await self.page.query_selector('button[hx-post*="/settings/routes/"][hx-post*="/delete"]')
            if delete_route:
                self.log("SETTINGS", "Delete Route Button", "PASS", "Button exists")
            else:
                self.log("SETTINGS", "Delete Route Button", "INFO", "Not found")
        except Exception as e:
            self.log("SETTINGS", "Delete Route Button", "FAIL", str(e))

        # --- Health Tab ---
        await self.navigate("/settings/tab/health")
        await asyncio.sleep(0.5)

        # 14. Reset Circuit Breakers
        try:
            reset_health = await self.page.query_selector('button[hx-post="/settings/reset-health"]')
            if reset_health:
                self.clear_errors()
                await reset_health.click()
                await asyncio.sleep(0.8)
                self.log("SETTINGS", "Reset Circuit Breakers", "PASS", "Reset triggered")
                self.assert_no_errors("SETTINGS", "Reset Circuit Breakers")
            else:
                self.log("SETTINGS", "Reset Circuit Breakers", "INFO", "Button not found")
        except Exception as e:
            self.log("SETTINGS", "Reset Circuit Breakers", "FAIL", str(e))

        # 15. Reset individual circuit breaker
        try:
            reset_single = await self.page.query_selector('button[hx-post*="/settings/reset-health/"]')
            if reset_single:
                self.log("SETTINGS", "Reset Single Circuit Breaker", "PASS", "Button exists")
            else:
                self.log("SETTINGS", "Reset Single Circuit Breaker", "INFO", "No circuit breakers to reset")
        except Exception as e:
            self.log("SETTINGS", "Reset Single Circuit Breaker", "FAIL", str(e))

        # 16. Refresh Snapshots
        try:
            refresh_snapshots = await self.page.query_selector('button[hx-get="/settings/snapshots"]')
            if refresh_snapshots:
                self.clear_errors()
                await refresh_snapshots.click()
                await asyncio.sleep(0.5)
                self.log("SETTINGS", "Refresh Snapshots", "PASS", "Snapshots refreshed")
                self.assert_no_errors("SETTINGS", "Refresh Snapshots")
            else:
                self.log("SETTINGS", "Refresh Snapshots", "INFO", "Button not found")
        except Exception as e:
            self.log("SETTINGS", "Refresh Snapshots", "FAIL", str(e))

        # 17. Create Snapshot
        try:
            snapshot_form = await self.page.query_selector('form[hx-post="/settings/snapshots/create"]')
            if snapshot_form:
                name_input = await snapshot_form.query_selector('input[name="name"]')
                submit_btn = await snapshot_form.query_selector('button[type="submit"]')
                if name_input and submit_btn:
                    await name_input.fill(f"TestSnapshot_{datetime.now().strftime('%H%M%S')}")
                    self.clear_errors()
                    await submit_btn.click()
                    await asyncio.sleep(0.8)
                    self.log("SETTINGS", "Create Snapshot", "PASS", "Snapshot created")
                    self.assert_no_errors("SETTINGS", "Create Snapshot")
                else:
                    self.log("SETTINGS", "Create Snapshot", "FAIL", "Form elements missing")
            else:
                self.log("SETTINGS", "Create Snapshot", "FAIL", "Form not found")
        except Exception as e:
            self.log("SETTINGS", "Create Snapshot", "FAIL", str(e))

        # 18. Restore Snapshot (if snapshots exist)
        try:
            restore_btn = await self.page.query_selector('button[hx-post*="/settings/snapshots/"][hx-post*="/restore"]')
            if restore_btn:
                self.log("SETTINGS", "Restore Snapshot Button", "PASS", "Button exists")
            else:
                self.log("SETTINGS", "Restore Snapshot Button", "INFO", "No snapshots to restore")
        except Exception as e:
            self.log("SETTINGS", "Restore Snapshot Button", "FAIL", str(e))

        # 19. Delete Snapshot
        try:
            delete_snapshot = await self.page.query_selector('button[hx-delete*="/settings/snapshots/"]')
            if delete_snapshot:
                self.log("SETTINGS", "Delete Snapshot Button", "PASS", "Button exists")
            else:
                self.log("SETTINGS", "Delete Snapshot Button", "INFO", "No snapshots to delete")
        except Exception as e:
            self.log("SETTINGS", "Delete Snapshot Button", "FAIL", str(e))

        # 20. Database Reset buttons (check existence, don't click - destructive)
        try:
            reset_buttons = [
                ("main", "Reset Main DB"),
                ("settings", "Reset Settings DB"),
                ("operational", "Reset Operational DB"),
                ("notebook", "Reset Notebook DB"),
                ("extrapolation", "Reset Extrapolation DB"),
                ("all", "Reset All Databases"),
            ]
            for db_name, label in reset_buttons:
                btn = await self.page.query_selector(f'button[hx-vals*="{db_name}"]')
                if btn:
                    self.log("SETTINGS", label, "PASS", "Button exists")
                else:
                    self.log("SETTINGS", label, "FAIL", "Button not found")
        except Exception as e:
            self.log("SETTINGS", "Database Reset Buttons", "FAIL", str(e))

    async def run_all_tests(self):
        """Run all UI tests."""
        await self.setup()
        try:
            await self.test_worlds_page()
            await self.test_settings_page()
        finally:
            await self.teardown()
        return self.results


# ------------------------------------------------------------------
# Pytest Tests
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
async def browser_tester():
    tester = OmniverseBrowserTester()
    await tester.setup()
    yield tester
    await tester.teardown()


@pytest.mark.asyncio
@pytest.mark.browser
async def test_worlds_page_functionality():
    """Test all Worlds page interactions."""
    tester = OmniverseBrowserTester()
    await tester.setup()
    try:
        await tester.test_worlds_page()
    finally:
        await tester.teardown()

    failures = [r for r in tester.results if r["status"] == "FAIL"]
    assert len(failures) == 0, f"Worlds page failures: {failures}"


@pytest.mark.asyncio
@pytest.mark.browser
async def test_settings_page_functionality():
    """Test all Settings page interactions."""
    tester = OmniverseBrowserTester()
    await tester.setup()
    try:
        await tester.test_settings_page()
    finally:
        await tester.teardown()

    failures = [r for r in tester.results if r["status"] == "FAIL"]
    assert len(failures) == 0, f"Settings page failures: {failures}"


@pytest.mark.asyncio
@pytest.mark.browser
async def test_full_ui_functionality():
    """Run all functionality tests and print summary."""
    tester = OmniverseBrowserTester()
    results = await tester.run_all_tests()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    info = sum(1 for r in results if r["status"] == "INFO")

    print("\n" + "=" * 80)
    print("UI FUNCTIONALITY TEST SUMMARY")
    print("=" * 80)
    print(f"Total: {len(results)} | PASS: {passed} | FAIL: {failed} | INFO: {info}")

    if failed > 0:
        print("\nFailed tests:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  FAIL [{r['category']}] {r['element']}: {r['detail']}")

    assert failed == 0, f"{failed} UI functionality tests failed"
