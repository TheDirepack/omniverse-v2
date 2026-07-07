import logging
import urllib.parse
from typing import Any

from bs4 import BeautifulSoup

from app.core.browser import browser_manager

SEARCH_URLS = {
    "google": "https://www.google.com/search?q={q}",
    "duckduckgo": "https://html.duckduckgo.com/html/?q={q}",
    "brave": "https://search.brave.com/search?q={q}",
}

MAX_RESULTS_PER_ENGINE = 10

# Generic phrases search engines show when they've served a bot-check/CAPTCHA
# instead of real results. Detecting this avoids the agent wrongly concluding
# "no results exist" when it was actually blocked, which is a very different
# situation (it should try a different engine or back off, not give up).
BOT_CHECK_PATTERNS = [
    "detected unusual traffic",
    "our systems have detected unusual traffic",
    "verify you are a human",
    "verify you're a human",
    "please verify you are human",
    "recaptcha",
    "/sorry/index",
    "unusual traffic from your computer network",
    "access to this page has been denied",
]

AI_CONTAINER_SELECTORS = [
    "[class*='ai']",
    "[class*='AI']",
    "[class*='featured']",
    "[class*='summary']",
    "[class*='answer']",
    "[id*='ai']",
    "[id*='featured']",
    "[id*='answer']",
]


class WebSearcher:
    async def perform_search(
        self,
        query: str,
        engine: str = "google",
        site_filter: str | None = None,
        max_results: int = 10,
    ) -> dict[str, Any]:
        if site_filter:
            query = f"site:{site_filter} {query}"

        url_template = SEARCH_URLS.get(engine)
        if not url_template:
            return {
                "status": "ERROR",
                "message": f"Unsupported engine: {engine}. Supported: {', '.join(SEARCH_URLS)}.",
            }

        search_url = url_template.format(q=urllib.parse.quote(query))

        page, context = await browser_manager.get_page()
        try:
            try:
                await page.goto(search_url, wait_until="networkidle", timeout=20000)
            except Exception as e:
                logging.warning(f"Search page load failed, retrying: {e}")
                await page.goto(
                    search_url, wait_until="domcontentloaded", timeout=15000
                )
            html = await page.content()

            lower_html = html.lower()
            if any(pattern in lower_html for pattern in BOT_CHECK_PATTERNS):
                return {
                    "status": "BLOCKED",
                    "engine": engine,
                    "message": (
                        f"Search engine {engine} appears to have shown a bot-verification "
                        f"page instead of search results for this query. Try a different engine "
                        f"({', '.join(e for e in SEARCH_URLS if e != engine)}) or a fetchPage on a known relevant URL."
                    ),
                }

            soup = BeautifulSoup(html, "html.parser")

            if engine == "google":
                results = self._parse_google(soup)
            elif engine == "duckduckgo":
                results = self._parse_duckduckgo(soup)
            elif engine == "brave":
                results = self._parse_brave(soup)
            else:
                results = []

            if results:
                return {
                    "status": "SUCCESS",
                    "engine": engine,
                    "query": query,
                    "results": results[:max_results],
                }
            return {
                "status": "NO_RESULTS",
                "engine": engine,
                "query": query,
                "message": f"No results found for {query} on {engine}. Try a different engine.",
            }
        finally:
            await page.close()
            await context.close()
            browser_manager.release_page(context)

    def _is_ai_container(self, element) -> bool:
        for selector in AI_CONTAINER_SELECTORS:
            # Check if element itself matches by checking if its parent matches it
            parent = element.parent
            if parent and parent.select_one(selector) == element:
                return True
        return False

    def _parse_google(self, soup: BeautifulSoup) -> list:
        results = []
        idx = 0

        for g in soup.select("div.g"):
            if self._is_ai_container(g):
                continue

            h3 = g.select_one("h3")
            if not h3:
                continue

            title = h3.get_text(" ", strip=True)
            if not title:
                continue

            link_el = g.select_one("a[href]")
            if not link_el:
                continue
            href = link_el.get("href", "")
            if href.startswith("/url?q="):
                href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get(
                    "q", [""]
                )[0]
            if not href or not href.startswith("http"):
                continue

            snippet_el = g.select_one("div.VwiC3b, span.st")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            idx += 1
            results.append({"title": title, "url": href, "snippet": snippet})

        return results

    def _parse_duckduckgo(self, soup: BeautifulSoup) -> list:
        results = []
        idx = 0

        for a in soup.select("a.result__a"):
            if self._is_ai_container(a):
                continue

            title = a.get_text(" ", strip=True)
            href = a.get("href", "")
            if not title or not href:
                continue

            result_div = a.find_parent(class_="result")
            snippet = ""
            if result_div:
                snip_el = result_div.select_one(".result__snippet")
                snippet = snip_el.get_text(" ", strip=True) if snip_el else ""

            idx += 1
            results.append({"title": title, "url": href, "snippet": snippet})

        return results

    def _parse_brave(self, soup: BeautifulSoup) -> list:
        results = []
        idx = 0

        for snippet_div in soup.select("div.snippet"):
            if self._is_ai_container(snippet_div):
                continue

            title_el = snippet_div.select_one("a[data-label='title'], a.snippet-title")
            if not title_el:
                continue

            title = title_el.get_text(" ", strip=True)
            href = title_el.get("href", "")
            if not title or not href.startswith("http"):
                continue

            desc_el = snippet_div.select_one(
                "div.snippet-description, p.snippet-description, div.description"
            )
            desc = desc_el.get_text(" ", strip=True) if desc_el else ""

            idx += 1
            results.append({"title": title, "url": href, "snippet": desc})

        if not results:
            for a in soup.select("a[href^='http']"):
                parent = a.find_parent("div")
                if not parent:
                    continue
                if self._is_ai_container(parent):
                    continue
                title = a.get_text(" ", strip=True)
                href = a.get("href", "")
                if not title or len(title) < 3:
                    continue
                desc_el = parent.select_one("p")
                desc = desc_el.get_text(" ", strip=True) if desc_el else ""
                idx += 1
                results.append({"title": title, "url": href, "snippet": desc})
                if idx >= 10:
                    break

        return results


web_searcher = WebSearcher()
