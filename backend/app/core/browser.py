import asyncio
import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from cloakbrowser import launch_async

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent browser operations

    async def start(self):
        # Intentionally a no-op: the browser binary is downloaded/launched lazily,
        # on the first call to get_page().
        return

    async def stop(self):
        if self.browser:
            await self.browser.close()
            self.browser = None

    async def _ensure_browser(self):
        if self.browser is not None:
            return
        # We use a lock to prevent multiple concurrent launches
        # Note: self._launch_lock needs to be initialized in __init__
        if not hasattr(self, '_launch_lock'):
            self._launch_lock = asyncio.Lock()
        async with self._launch_lock:
            if self.browser is None:
                self.browser = await launch_async()

    async def get_page(self):
        await self._ensure_browser()
        
        await self.semaphore.acquire()
        try:
            context = await self.browser.new_context()
            page = await context.new_page()
            return page, context
        except Exception as e:
            logging.exception("Failed to create browser page/context")
            self.semaphore.release()
            raise

    @asynccontextmanager
    async def page(self) -> AsyncGenerator[any, None]:
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
        self.semaphore.release()
        # Note: The caller is responsible for closing the page and context.

browser_manager = BrowserManager()
