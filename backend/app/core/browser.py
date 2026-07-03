import asyncio
from typing import Optional
from cloakbrowser import launch_async

class BrowserManager:
    def __init__(self):
        self.browser = None
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent browser operations

    async def start(self):
        if self.browser is None:
            self.browser = await launch_async()

    async def stop(self):
        if self.browser:
            await self.browser.close()
            self.browser = None

    async def get_page(self):
        if self.browser is None:
            raise RuntimeError("BrowserManager not started. Call start() first.")
        
        # We use a semaphore to limit the number of concurrent pages/contexts
        # and avoid overloading the system or triggering anti-bot protections.
        await self.semaphore.acquire()
        try:
            context = await self.browser.new_context()
            page = await context.new_page()
            return page, context
        except Exception:
            self.semaphore.release()
            raise

    def release_page(self, context):
        self.semaphore.release()
        # Note: The caller is responsible for closing the page and context.

browser_manager = BrowserManager()
