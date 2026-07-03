from app.core.browser import browser_manager
import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup
from sqlmodel import Session, select

from app.db.session import engine
from app.db.schema import Setting


class WebSearcher:
    def get_setting(self, key: str) -> Optional[str]:
        with Session(engine) as session:
            setting = session.exec(select(Setting).where(Setting.key == key)).first()
            return setting.value if setting else None

    async def perform_search(self, query: str) -> str:
        search_query = f"{query} lore wiki official database"
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"
        
        # Use browser_manager instead of relaunching browser
        page, context = await browser_manager.get_page()
        try:
            await page.goto(search_url, wait_until="networkidle")
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            results: list[str] = []
            for idx, result in enumerate(soup.select("a.result__a")[:5]):
                title = result.get_text(" ", strip=True)
                link = result.get("href", "")
                snippet_el = result.find_parent(class_="result").select_one(".result__snippet") if result.find_parent(class_="result") else None
                snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
                if title and link:
                    results.append(f"### {idx + 1}. [{title}]({link})\n{snippet}\n")
            if results:
                return "\n".join(results)
            return f"No authoritative lore indices found for {query}."
        finally:
            await page.close()
            await context.close()
            browser_manager.release_page(context)


web_searcher = WebSearcher()
