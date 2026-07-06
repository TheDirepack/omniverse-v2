import re
import logging
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import socket
import trafilatura
from app.core.browser import browser_manager

# Patterns for detecting cookie/consent pages
COOKIE_PATTERNS = [
    "we value your privacy",
    "cookie settings",
    "manage cookies",
    "consent preferences",
    "your privacy choices",
    "accept all",
    "reject all",
    "legitimate interest",
]

# Button text to look for when dismissing banners
DISMISS_BUTTON_TEXTS = [
    "Reject All",
    "Reject",
    "Decline",
    "Necessary Only",
    "Continue without accepting",
    "Accept All", # Fallback
]

# Tags to be aggressively removed
NOISE_TAGS = [
    "script", "style", "nav", "footer", "iframe", "noscript", "header",
    "aside", "dialog", "form", "menu", "svg", "canvas", "picture",
    "button", "input", "label"
]

# Namespaces and keywords to ignore in links (Infrastructure/Meta)
IGNORE_LINK_PATTERNS = [
    r"^Special:", r"^Talk:", r"^User:", r"^File:", r"^Media:", 
    r"^Template:", r"^Category:", r"^Help:", r"^Project:",
    r"/History", r"/Edit", r"/WhatLinksHere", r"/Action/edit",
    r"Special:RecentChanges", r"Special:PermanentLink"
]

# Priority mapping for link types
LINK_PRIORITY_MAP = {
    "ARTICLE": "High",
    "INFOBOX": "High",
    "SEE_ALSO": "High",
    "CATEGORY": "Medium",
    "REFERENCE": "Medium",
    "OTHER": "Low"
}

# CSS selectors for common consent/cookie overlays
NOISE_SELECTORS = [
    "[id*='cookie']", "[class*='cookie']",
    "[id*='consent']", "[class*='consent']",
    "[id*='gdpr']", "[class*='gdpr']",
    ".cookie-banner", ".consent-modal", ".privacy-overlay"
]

# Patterns below are intentionally generic (not tied to any single wiki host)
# so freshness detection keeps working as wikis move between MediaWiki,
# Fandom, Miraheze, Wikitide, custom static sites, etc.
LAST_EDITED_PATTERNS = [
    r"[Tt]his page was last edited on\s+([^.\n]{6,40})",   # MediaWiki/Fandom footer
    r"[Ll]ast (?:edited|modified|updated)[:\s]+([^\n\|]{6,40})",  # generic footer/infobox
    r"[Pp]age last (?:changed|updated)[:\s]+([^\n\|]{6,40})",
]

MOVED_OR_STALE_PATTERNS = [
    r"[Tt]his wiki has (?:moved|migrated) to",
    r"[Tt]his (?:site|wiki) is no longer (?:maintained|updated|active)",
    r"[Aa]rchived (?:version|copy|snapshot) of",
    r"[Pp]lease (?:visit|see|use) (?:the )?(?:new|official|updated) (?:wiki|site) at",
    r"[Tt]his (?:wiki|page) is (?:outdated|deprecated|obsolete)",
    r"content (?:has been|was) (?:merged|moved) (?:into|to)",
]

CANONICAL_LINK_PATTERN = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)

logger = logging.getLogger(__name__)


def _extract_freshness_signals(url: str, final_url: str, html: str, text: str, last_modified_header: str | None) -> str:
    lines = [f"Requested URL: {url}", f"Final URL after redirects: {final_url}"]
    if final_url != url:
        lines.append("Redirect occurred: YES (the site may have moved domains/paths; check whether the final URL is the actively maintained one).")
    else:
        lines.append("Redirect occurred: NO")

    lines.append(f"HTTP Last-Modified header: {last_modified_header or 'not provided by server'}")

    canon_match = CANONICAL_LINK_PATTERN.search(html)
    if canon_match:
        lines.append(f"Canonical link tag points to: {canon_match.group(1)}")

    edited_dates = []
    for pat in LAST_EDITED_PATTERNS:
        for m in re.finditer(pat, text):
            edited_dates.append(m.group(1).strip())
    if edited_dates:
        lines.append(f"On-page 'last edited' text found: {edited_dates[:3]}")
    else:
        lines.append("On-page 'last edited' text found: none detected")

    stale_hits = []
    for pat in MOVED_OR_STALE_PATTERNS:
        if re.search(pat, text):
            stale_hits.append(pat)
    if stale_hits:
        lines.append("STALENESS WARNING: page text suggests this source has moved, is archived, or is no longer maintained. Prefer the actively maintained source if one is found elsewhere.")
    else:
        lines.append("Staleness warning: none detected")

    return "[SOURCE FRESHNESS SIGNALS]\n" + "\n".join(lines) + "\n[END SIGNALS]\n"


class WebFetcher:
    async def _dismiss_cookie_banners(self, page):
        """Attempt to dismiss cookie banners by clicking known 'reject' buttons."""
        try:
            for text in DISMISS_BUTTON_TEXTS:
                # Use a case-insensitive regex for the button name
                button = page.get_by_role("button", name=re.compile(text, re.IGNORECASE), exact=False).first
                if await button.is_visible():
                    await button.click()
                    await asyncio.sleep(0.5)
                    return True
            # Fallback: try Escape key
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.debug(f"Error dismissing cookie banners: {e}")
        return False

    def _is_cookie_page(self, text: str) -> bool:
        """Check if the text is dominated by cookie/consent vocabulary."""
        if not text:
            return False
        
        first_1000 = text[:1000].lower()
        matches = sum(1 for pat in COOKIE_PATTERNS if pat in first_1000)
        
        # If 3 or more patterns match in the first 1000 chars, it's likely a cookie page
        return matches >= 3

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize repeated whitespace to reduce token usage."""
        # Replace 3+ newlines with 2, and 2+ spaces with 1
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def _extract_internal_links(self, soup: BeautifulSoup, base_url: str, max_links: int = 20) -> List[Dict[str, Any]]:
        """Extract, classify, and score internal links for research discovery."""
        links_data = {} # (url, title) -> {"score": 0, "tier": "Low", "sections": set()}
        
        # Identify high-value areas
        high_value_selectors = [
            "main", "article", ".infobox", ".mw-parser-output",
            "[id*='seealso']", "[class*='seealso']", "[id*='references']", "[class*='references']"
        ]
        medium_value_selectors = [
            ".catlinks", ".navbox", ".navmenu", ".category-list"
        ]
        
        # To avoid duplicates and junk
        discard_keywords = {"privacy", "terms", "policy", "help", "login", "signup", "register", "about", "contact", "discord", "twitter", "facebook"}
        
        all_links = soup.find_all("a", href=True)
        
        for a in all_links:
            href = a['href']
            absolute_url = urljoin(base_url, href)
            title = a.get_text(strip=True)
            if not title or not href:
                continue
            
            # 1. FILTER: Infrastructure/Meta links
            if any(re.search(pat, href, re.IGNORECASE) for pat in IGNORE_LINK_PATTERNS) or \
               any(re.search(pat, title, re.IGNORECASE) for pat in IGNORE_LINK_PATTERNS):
                continue
            
            # Only internal links (relative or same domain)
            if absolute_url.startswith("http") and not absolute_url.startswith(soup.find("base")["href"] if soup.find("base") else ""):
                if not any(sel in str(a.find_parent()).lower() for sel in ["references", "citations"]):
                    continue
            
            # Filter out junk by title/href
            if any(kw in title.lower() or kw in href.lower() for kw in discard_keywords):
                continue
                
            # 2. CLASSIFY & TIER
            tier = "Low"
            parent_html = str(a.find_parent()).lower()
            
            if any(sel in parent_html for sel in high_value_selectors) or a.find_parent("main") or a.find_parent("article"):
                tier = "High"
            elif any(sel in parent_html for sel in medium_value_selectors) or "category" in parent_html:
                tier = "Medium"
                
            # Scoring and aggregation
            key = (absolute_url, title)
            if key not in links_data:
                links_data[key] = {"score": 0, "tier": tier, "sections": set()}
            
            links_data[key]["score"] += 1
            
            # Try to find a section heading for this link
            curr = a
            while curr and curr.name != "body":
                if curr.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    links_data[key]["sections"].add(curr.get_text(strip=True))
                    break
                if curr.name in ["p", "div", "li", "table", "ul", "ol"]:
                    prev = curr.find_previous_sibling()
                    while prev and prev.name != "body":
                        if prev.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                            links_data[key]["sections"].add(prev.get_text(strip=True))
                            break
                        prev = prev.find_previous_sibling()
                curr = curr.find_parent()
        
        # Sort by tier (High > Medium > Low) and then by score
        tier_priority = {"High": 3, "Medium": 2, "Low": 1}
        sorted_links = sorted(
            links_data.items(), 
            key=lambda x: (tier_priority.get(x[1]["tier"], 0), x[1]["score"]), 
            reverse=True
        )
        
        results = []
        for (url, title), data in sorted_links[:max_links]:
            results.append({
                "url": url,
                "title": title,
                "tier": data["tier"],
                "score": data["score"],
                "sections": list(data["sections"])[:2]
            })
            
        return results


    def _extract_text_from_soup(self, soup: BeautifulSoup) -> str:
        """Basic text extraction with noise stripping for cookie detection."""
        # Work on a copy to avoid mutating the original soup used for signals
        temp_soup = BeautifulSoup(str(soup), "html.parser")
        for tag in temp_soup(NOISE_TAGS):
            tag.decompose()
        
        # Remove elements matching noise selectors
        for selector in NOISE_SELECTORS:
            for element in temp_soup.select(selector):
                element.decompose()
                
        text = temp_soup.get_text()
        # Strip wiki template scaffolding like {{{variable}}}
        text = re.sub(r'\{\{[^}]*\}\}', '', text)
        
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return self._normalize_whitespace(text)

    def _extract_research_signals(self, soup: BeautifulSoup) -> str:
        """Extract research-critical navigation like 'See Also', Categories, etc."""
        signals = []
        
        # 1. Look for 'See Also' or 'Related' sections
        for heading in soup.find_all(["h2", "h3", "h4"]):
            h_text = heading.get_text().strip().lower()
            if "see also" in h_text or "related" in h_text or "further reading" in h_text:
                sibling = heading.find_next_sibling()
                if sibling:
                    signals.append(f"--- {heading.get_text().strip()} ---\n{sibling.get_text(separator='\n', strip=True)}")
        
        # 2. Extract Categories (common in wikis)
        cat_div = soup.find("div", class_="catlinks") or \
                  soup.find("div", class_="categories") or \
                  soup.find("div", id="mw-category")
        if cat_div:
            signals.append(f"--- Categories ---\n{cat_div.get_text(separator='\n', strip=True)}")
        
        # 3. Extract Breadcrumbs
        breadcrumb = soup.find("nav", {"aria-label": "Breadcrumb"}) or \
                     soup.find("div", {"class": "breadcrumbs"})
        if breadcrumb:
            signals.append(f"--- Breadcrumbs ---\n{breadcrumb.get_text(separator=' > ', strip=True)}")
        
        # 4. Extract Infobox links (common in wikis)
        infobox = soup.find("table", {"class": "infobox"})
        if infobox:
            text = infobox.get_text(separator='\n', strip=True)
            # Omit hollow infoboxes (containing only placeholders or very little content)
            if len(text) > 50 and not (text.count('{{{') > text.count('word')):
                signals.append(f"--- Infobox Summary ---\n{text}")
        
        return "\n\n".join(signals)


    def _detect_page_type(self, html: str, text: str) -> str:
        """Detect if the page is a known non-article type."""
        text_low = text.lower()
        if "captcha" in text_low or "robot" in text_low and "verify" in text_low:
            return "CAPTCHA"
        if "404" in text_low and "not found" in text_low:
            return "404 NOT FOUND"
        if "login" in text_low and ("password" in text_low or "username" in text_low) and len(text) < 5000:
            return "LOGIN PAGE"
        if "search results" in text_low or "results for" in text_low:
            return "SEARCH RESULTS"
        return "ARTICLE"

    async def fetch_page(self, url: str, include_freshness: bool = True, max_links: int = 20) -> Dict[str, Any]:
        # SSRF Protection
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid protocol: {parsed.scheme}. Only http and https are allowed.")
        
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: hostname missing.")
        
        internal_hostnames = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"}
        if hostname.lower() in internal_hostnames or hostname.lower().endswith(".local"):
            raise ValueError(f"Access to internal resource {hostname} is forbidden.")
        
        try:
            ip = socket.gethostbyname(hostname)
            if ip.startswith(("127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "192.168.")) or ip == "169.254.169.254":
                raise ValueError(f"Access to private IP {ip} is forbidden.")
        except socket.gaierror:
            pass
        
        # Use browser_manager instead of relaunching browser
        page, context = await browser_manager.get_page()
        try:
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception as e:
                logger.debug(f"networkidle timeout for {url}, falling back to domcontentloaded: {e}")
                response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # 1. Initial cookie dismissal attempt
            await self._dismiss_cookie_banners(page)
            
            html = await page.content()
            final_url = page.url
            last_modified_header = None
            if response is not None:
                try:
                    last_modified_header = response.headers.get("last-modified")
                except Exception as e:
                    logger.debug(f"Failed to get last-modified header for {url}: {e}")
                    last_modified_header = None
  
            soup = BeautifulSoup(html, "html.parser")
            
            # 2. Detect if it's still a cookie page
            text_for_detection = self._extract_text_from_soup(soup)
            if self._is_cookie_page(text_for_detection):
                logger.info(f"Cookie page detected for {url}. Attempting second dismissal...")
                await self._dismiss_cookie_banners(page)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                text_for_detection = self._extract_text_from_soup(soup)
  
            # 3. Page Type Detection
            page_type = self._detect_page_type(html, text_for_detection)
            if page_type != "ARTICLE":
                return {
                    "page_type": page_type,
                    "main_content": text_for_detection[:1000],
                    "error": f"Page is identified as {page_type}, not a standard article."
                }
  
            # 4. Semantic Extraction
            # Main Article via trafilatura
            main_article = trafilatura.extract(html) or ""
            if not main_article:
                # Fallback to basic extraction if trafilatura fails
                main_article = text_for_detection
            
            # Clean up literal \n sequences that may have been escaped in source or by extraction
            main_article = main_article.replace('\\n', '\n')
            
            # Internal Links (The Topology)
            links = self._extract_internal_links(soup, final_url, max_links=max_links)
            
            # Research Signals via custom logic
            signals = self._extract_research_signals(soup)
            signals = signals.replace('\\n', '\n')
            
            result = {
                "metadata": {
                    "url": final_url,
                    "word_count": len(main_article.split()),
                    "page_type": page_type,
                },
                "main_content": main_article,
                "internal_links": links,
                "research_signals": signals,
                "freshness": None if not include_freshness else _extract_freshness_signals(url, final_url, html, main_article, last_modified_header)
            }
            
            return result
        finally:
            await page.close()
            await context.close()
            browser_manager.release_page(context)




web_fetcher = WebFetcher()
