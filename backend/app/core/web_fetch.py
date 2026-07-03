from bs4 import BeautifulSoup
from app.core.browser import browser_manager

class WebFetcher:
    async def fetch_page(self, url: str) -> str:
        # Use browser_manager instead of relaunching browser
        page, context = await browser_manager.get_page()
        try:
            await page.goto(url, wait_until="networkidle")
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript", "header"]):
                tag.decompose()
            text = "\n".join(line.strip() for line in soup.get_text().splitlines() if line.strip())
            if len(text) > 20000:
                return text[:20000] + "\n... [truncated at 20,000 characters]"
            return text
        finally:
            await page.close()
            await context.close()
            browser_manager.release_page(context)


web_fetcher = WebFetcher()
