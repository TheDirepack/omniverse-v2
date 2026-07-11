import asyncio
import hashlib
import logging
import re
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import trafilatura
from bs4 import BeautifulSoup

from app.core.browser import browser_manager
from app.core.runtime_state import is_aborted


class WebFetchError(ValueError):
    """Base exception for web fetch errors."""
    pass

class InvalidProtocolError(WebFetchError):
    def __init__(self, message="Invalid protocol"):
        super().__init__(message)

class HostnameMissingError(WebFetchError):
    def __init__(self, message="Hostname missing"):
        super().__init__(message)

class InternalResourceError(WebFetchError):
    def __init__(self, message="Internal resource forbidden"):
        super().__init__(message)

class PrivateIPError(WebFetchError):
    def __init__(self, message="Private IP forbidden"):
        super().__init__(message)

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
    "Accept All",  # Fallback
]

# Tags to be aggressively removed
NOISE_TAGS = [
    "script",
    "style",
    "nav",
    "footer",
    "iframe",
    "noscript",
    "header",
    "aside",
    "dialog",
    "form",
    "menu",
    "svg",
    "canvas",
    "picture",
    "button",
    "input",
    "label",
]

# Namespaces and keywords to ignore in links (Infrastructure/Meta)
IGNORE_LINK_PATTERNS = [
    r"^Special:",
    r"^Talk:",
    r"^User:",
    r"^File:",
    r"^Media:",
    r"^Template:",
    r"^Category:",
    r"^Help:",
    r"^Project:",
    r"/History",
    r"/Edit",
    r"/WhatLinksHere",
    r"/Action/edit",
    r"Special:RecentChanges",
    r"Special:PermanentLink",
]

# Priority mapping for link types
LINK_PRIORITY_MAP = {
    "ARTICLE": "High",
    "INFOBOX": "High",
    "SEE_ALSO": "High",
    "CATEGORY": "Medium",
    "REFERENCE": "Medium",
    "OTHER": "Low",
}

# CSS selectors for common consent/cookie overlays
NOISE_SELECTORS = [
    "[id*='cookie']",
    "[class*='cookie']",
    "[id*='consent']",
    "[class*='consent']",
    "[id*='gdpr']",
    "[class*='gdpr']",
    ".cookie-banner",
    ".consent-modal",
    ".privacy-overlay",
]

# Patterns below are intentionally generic (not tied to any single wiki host)
# so freshness detection keeps working as wikis move between MediaWiki,
# Fandom, Miraheze, Wikitide, custom static sites, etc.
LAST_EDITED_PATTERNS = [
    r"[Tt]his page was last edited on\s+([^.\n]{6,40})",  # MediaWiki/Fandom footer
    r"[Ll]ast (?:edited|modified|updated)[:\s]+([^\n\|]{6,40})",
# generic footer/infobox
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

CANONICAL_LINK_PATTERN = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', re.IGNORECASE
)

logger = logging.getLogger(__name__)


def _extract_freshness_signals(
    url: str, final_url: str, html: str, text: str, last_modified_header: str | None
) -> str:
    lines = [f"Requested URL: {url}", f"Final URL after redirects: {final_url}"]
    if final_url != url:
        lines.append(
            "Redirect occurred: YES (the site may have moved domains/paths; "
"check whether the final URL is the actively maintained one)."
        )
    else:
        lines.append("Redirect occurred: NO")

    lines.append(
        f"HTTP Last-Modified header: {last_modified_header or 'not provided by server'}"
    )

    canon_match = CANONICAL_LINK_PATTERN.search(html)
    if canon_match:
        lines.append(f"Canonical link tag points to: {canon_match.group(1)}")

    edited_dates = [
        m.group(1).strip()
        for pat in LAST_EDITED_PATTERNS
        for m in re.finditer(pat, text)
    ]
    if edited_dates:
        lines.append(f"On-page 'last edited' text found: {edited_dates[:3]}")
    else:
        lines.append("On-page 'last edited' text found: none detected")

    stale_hits = [pat for pat in MOVED_OR_STALE_PATTERNS if re.search(pat, text)]
    if stale_hits:
        lines.append(
            "STALENESS WARNING: page text suggests this source has moved, "
            "is archived, or is no longer maintained. Prefer the actively "
            "maintained source if one is found elsewhere."
        )
    else:
        lines.append("Staleness warning: none detected")


    return "[SOURCE FRESHNESS SIGNALS]\n" + "\n".join(lines) + "\n[END SIGNALS]\n"


class WebFetcher:
    async def _dismiss_cookie_banners(self, page):
        """Attempt to dismiss cookie banners by clicking known 'reject' buttons."""
        try:
            for text in DISMISS_BUTTON_TEXTS:
                # Use a case-insensitive regex for the button name
                button = page.get_by_role(
                    "button", name=re.compile(text, re.IGNORECASE), exact=False
                ).first
                if await button.is_visible():
                    await button.click()
                    await asyncio.sleep(0.5)
                    return True
            # Fallback: try Escape key
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.debug("Error dismissing cookie banners: %s", e)
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
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def _apply_html_filtering(
        self, soup: BeautifulSoup, filtering: dict[str, Any] | None
    ) -> BeautifulSoup:
        """Apply domain-specific or custom filtering to the soup."""
        if not filtering:
            return soup

        # Copy soup to avoid mutating original
        work_soup = BeautifulSoup(str(soup), "html.parser")

        preset = filtering.get("preset")
        if preset == "trafilatura":
            return soup # handled separately in fetch_page

        # Preset Cleanup Profiles
        if preset == "wiki":
            wiki_selectors = [
                ".mw-editsection", ".mw-jump-link", ".navbox", ".catlinks"
            ]
            for selector in wiki_selectors:
                for el in work_soup.select(selector):
                    el.decompose()
        elif preset == "forum":
            for selector in [".user-profile", ".forum-nav", ".footer-links"]:
                for el in work_soup.select(selector):
                    el.decompose()
        elif preset == "official_docs":
            for selector in [".sidebar", ".toc", ".footer"]:
                for el in work_soup.select(selector):
                    el.decompose()

        # Custom filtering
        include_tags = filtering.get("include_tags")
        if include_tags:
            for tag in work_soup.find_all():
                if tag.name not in include_tags and tag.name not in ["body", "html"]:
                    tag.decompose()

        css_selectors = filtering.get("css_selectors")
        if css_selectors:
            for selector in css_selectors:
                for el in work_soup.select(selector):
                    el.decompose()

        exclude_tags = filtering.get("exclude_tags")
        if exclude_tags:
            for tag_name in exclude_tags:
                for tag in work_soup.find_all(tag_name):
                    tag.decompose()

        return work_soup

    def _extract_infobox(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract key-value pairs from common infobox classes."""
        infobox = soup.find("table", class_=["infobox", "portable-infobox"])
        if not infobox:
            return {}

        data = {}
        rows = infobox.find_all("tr")
        for row in rows:
            th = row.find("th")
            td = row.find("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                if key and val:
                    data[key] = val
        return data

    def _extract_tables(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Convert HTML tables into high-fidelity markdown tables."""
        tables = []
        for table in soup.find_all("table"):
            # Skip infoboxes as they are handled separately
            if "infobox" in table.get("class", []):
                continue

            caption = table.find("caption")
            caption_text = caption.get_text(strip=True) if caption else ""

            rows = table.find_all("tr")
            if not rows:
                continue

            headers = []
            # Try to find headers in the first row
            first_row = rows[0]
            th_elements = first_row.find_all(["th", "td"])
            headers = [th.get_text(strip=True) for th in th_elements]

            # Simple markdown conversion
            md_rows = []
            for row in rows:
                cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                md_rows.append("| " + " | ".join(cells) + " |")

            if len(headers) > 0:
                separator = "| " + " | ".join(["---"] * len(headers)) + " |"
                md_rows.insert(1, separator)

            tables.append({
                "caption": caption_text,
                "headers": headers,
                "markdown": "\n".join(md_rows)
            })
        return tables

    def _extract_references(self, soup: BeautifulSoup) -> list[str]:
        """Extract footnotes, citations, and external links."""
        refs = []
        # Common reference containers
        ref_pattern = re.compile(r"references|footnotes", re.IGNORECASE)
        ref_sections = soup.find_all("div", id=ref_pattern)
        if not ref_sections:
            ref_sections = soup.find_all("ol", class_=ref_pattern)

        for section in ref_sections:
            refs.extend(
                li.get_text(strip=True) for li in section.find_all("li")
            )

        return refs

    def _extract_weighted_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict[str, Any]]:
        """
        Score links based on location:
        Citation=10, See Also=8, Body=5, Nav=1, Footer=0.
        """
        links = []
        all_links = soup.find_all("a", href=True)

        for a in all_links:
            url = urljoin(base_url, a["href"])
            title = a.get_text(strip=True)
            if not title:
                continue

            score = 5 # Default: Body

            # Check context for scoring
            parent_text = str(a.find_parent()).lower()
            grandparent_text = (
                str(a.find_parent().find_parent()).lower()
                if a.find_parent()
                else ""
            )

            full_context = (parent_text + grandparent_text).lower()

            if any(kw in full_context for kw in ["reference", "citation", "footnote"]):
                score = 10
            elif any(
                kw in full_context
                for kw in ["see also", "related links", "further reading"]
            ):
                score = 8
            elif any(
                kw in full_context for kw in ["nav", "navigation", "menu", "sidebar"]
            ):
                score = 1
            elif any(kw in full_context for kw in ["footer", "copyright", "bottom"]):
                score = 0

            links.append({
                "url": url,
                "title": title,
                "score": score
            })

        return sorted(links, key=lambda x: x["score"], reverse=True)[:50]

    def _parse_structured_document(
        self, soup: BeautifulSoup, base_url: str, filtering: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Main structural parsing logic."""
        filtered_soup = self._apply_html_filtering(soup, filtering)

        # 1. Extract global elements
        infobox = self._extract_infobox(filtered_soup)
        tables = self._extract_tables(filtered_soup)
        references = self._extract_references(filtered_soup)
        internal_links = self._extract_weighted_links(filtered_soup, base_url)

        # 2. Sectioning
        sections = []
        # Find all headings (h1, h2, h3)
        headings = filtered_soup.find_all(["h1", "h2", "h3"])

        if not headings:
            # If no headings, treat the whole body as one section
            body = filtered_soup.find("body") or filtered_soup
            sections.append({
                "title": "Main Content",
                "heading_level": 1,
                "content": self._extract_text_from_soup(body),
                "importance": "High"
            })
        else:
            for i, heading in enumerate(headings):
                level = int(heading.name[1])
                title = heading.get_text(strip=True)

                # Content is everything between this heading and the next
                content_parts = []
                curr = heading.find_next_sibling()
                while curr and (i + 1 == len(headings) or curr != headings[i+1]):
                    if curr.name in ["h1", "h2", "h3"]:
                        break
                    content_parts.append(curr.get_text(separator="\n", strip=True))
                    curr = curr.find_next_sibling()

                content = "\n\n".join(content_parts)

                # De-duplication of paragraphs
                unique_paragraphs = []
                seen_hashes = set()
                for p in content.split("\n\n"):
                    p_clean = p.strip()
                    if not p_clean:
                        continue
                    h = hashlib.md5(p_clean.encode()).hexdigest()
                    if h not in seen_hashes:
                        unique_paragraphs.append(p_clean)
                        seen_hashes.add(h)

                content = "\n\n".join(unique_paragraphs)

                sections.append({
                    "title": title,
                    "heading_level": level,
                    "content": content,
                    "importance": (
                        "High" if level == 1 else "Medium" if level == 2 else "Low"
                    )
                })

        # Overview: first paragraph of first section or first 500 chars of text
        overview = ""
        if sections:
            first_sec_content = sections[0]["content"]
            overview = first_sec_content.split("\n\n")[0] if first_sec_content else ""
        if not overview:
            overview = self._extract_text_from_soup(filtered_soup)[:500]

        # Word count
        total_text = " ".join([s["content"] for s in sections])
        word_count = len(total_text.split())

        return {
            "metadata": {
                "url": base_url,
                "word_count": word_count,
                "page_type": "ARTICLE", # simplified for now
            },
            "overview": overview,
            "sections": sections,
            "tables": tables,
            "infobox": infobox,
            "references": references,
            "internal_links": internal_links,
        }


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
        text = re.sub(r"\{\{[^}]*\}\}", "", text)

        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return self._normalize_whitespace(text)

    def _extract_research_signals(self, soup: BeautifulSoup) -> str:
        """Extract research-critical navigation like 'See Also', Categories, etc."""
        signals = []

        # 1. Look for 'See Also' or 'Related' sections
        for heading in soup.find_all(["h2", "h3", "h4"]):
            h_text = heading.get_text().strip().lower()
            if (
                "see also" in h_text
                or "related" in h_text
                or "further reading" in h_text
            ):
                sibling = heading.find_next_sibling()
                if sibling:
                    sep = '\n'
                    signals.append(
                        f"--- {heading.get_text().strip()} ---\n"
                        f"{sibling.get_text(separator=sep, strip=True)}"
                    )

        # 2. Extract Categories (common in wikis)
        cat_div = (
            soup.find("div", class_="catlinks")
            or soup.find("div", class_="categories")
            or soup.find("div", id="mw-category")
        )
        if cat_div:
            sep = '\n'
            signals.append(
                f"--- Categories ---\n{cat_div.get_text(separator=sep, strip=True)}"
            )

        # 3. Extract Breadcrumbs
        breadcrumb = soup.find("nav", {"aria-label": "Breadcrumb"}) or soup.find(
            "div", {"class": "breadcrumbs"}
        )
        if breadcrumb:
            signals.append(
                f"--- Breadcrumbs ---\n"
                f"{breadcrumb.get_text(separator=' > ', strip=True)}"
            )

        # 4. Extract Infobox links (common in wikis)
        infobox = soup.find("table", {"class": "infobox"})
        if infobox:
            text = infobox.get_text(separator="\n", strip=True)
            # Omit hollow infoboxes
            # (containing only placeholders or very little content)
            if len(text) > 50 and not (text.count("{{{") > text.count("word")):
                signals.append(f"--- Infobox Summary ---\n{text}")

        return "\n\n".join(signals)

    def _detect_page_type(self, _html: str, text: str) -> str:
        """Detect if the page is a known non-article type."""
        text_low = text.lower()
        if "captcha" in text_low or ("robot" in text_low and "verify" in text_low):
            return "CAPTCHA"
        if "404" in text_low and "not found" in text_low:
            return "404 NOT FOUND"
        if (
            "login" in text_low
            and ("password" in text_low or "username" in text_low)
            and len(text) < 5000
        ):
            return "LOGIN PAGE"
        if "search results" in text_low or "results for" in text_low:
            return "SEARCH RESULTS"
        return "ARTICLE"

    async def fetch_page(
        self,
        url: str,
        include_freshness: bool = True,
        _max_links: int = 20,
        run_id: str | None = None,
        html_filtering: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # SSRF Protection
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise InvalidProtocolError()

        hostname = parsed.hostname
        if not hostname:
            raise HostnameMissingError()

        internal_hostnames = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"}
        if hostname.lower() in internal_hostnames or hostname.lower().endswith(
            ".local"
        ):
            raise InternalResourceError()

        try:
            if run_id and await is_aborted(run_id):
                raise RuntimeError("Aborted")

            ip = socket.gethostbyname(hostname)
            if (
                ip.startswith(
                    (
                        "127.",
                        "10.",
                        "172.16.",
                        "172.17.",
                        "172.18.",
                        "172.19.",
                        "172.20.",
                        "172.21.",
                        "172.22.",
                        "172.23.",
                        "172.24.",
                        "172.25.",
                        "172.26.",
                        "172.27.",
                        "172.28.",
                        "172.29.",
                        "172.30.",
                        "172.31.",
                        "192.168.",
                    )
                )
                or ip == "169.254.169.254"
            ):
                raise PrivateIPError()
        except socket.gaierror:
            pass

        # Use browser_manager instead of relaunching browser
        page, context = await browser_manager.get_page()
        try:
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=20000)
            except Exception as e:
                logger.debug(
                    "networkidle timeout for %s, falling back to domcontentloaded: %s",
                    url, e
                )
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=15000
                )

            # 1. Initial cookie dismissal attempt
            if run_id and await is_aborted(run_id):
                raise RuntimeError("Aborted")
            await self._dismiss_cookie_banners(page)

            html = await page.content()
            final_url = page.url
            last_modified_header = None
            if response is not None:
                try:
                    last_modified_header = response.headers.get("last-modified")
                except Exception as e:
                    logger.debug(
                        "Failed to get last-modified header for %s: %s", url, e
                    )
                    last_modified_header = None

            soup = BeautifulSoup(html, "html.parser")

            # 2. Detect if it's still a cookie page
            if run_id and await is_aborted(run_id):
                raise RuntimeError("Aborted")
            text_for_detection = self._extract_text_from_soup(soup)
            if self._is_cookie_page(text_for_detection):
                logger.info(
                    "Cookie page detected for %s. Attempting second dismissal...", url
                )
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
                     "error": (
                         f"Page is identified as {page_type}, "
                         "not a standard article."
                     ),
                }

            # 4. Extraction
            preset = (html_filtering or {}).get("preset")
            if preset == "trafilatura":
                # Basic flat extraction via trafilatura
                main_article = trafilatura.extract(html) or text_for_detection
                main_article = main_article.replace("\\n", "\n")

                result = {
                    "metadata": {
                        "url": final_url,
                        "word_count": len(main_article.split()),
                        "page_type": page_type,
                    },
                    "main_content": main_article,
                    "internal_links": self._extract_weighted_links(soup, final_url),
                     "research_signals": (
                         self._extract_research_signals(soup).replace("\\n", "\n")
                     ),
                      "freshness": (
                          None if not include_freshness else
                          _extract_freshness_signals(
                              url, final_url, html, main_article, last_modified_header
                          )
                      ),

                }
            else:
                # Structured parsing
                result = self._parse_structured_document(
                    soup, final_url, html_filtering
                )

                if include_freshness:
                    # Use a placeholder text for freshness signals because
                    # _extract_freshness_signals expects 'text'
                    combined_text = " ".join([s["content"] for s in result["sections"]])
                    result["freshness"] = _extract_freshness_signals(
                        url, final_url, html, combined_text, last_modified_header
                    )
                else:
                    result["freshness"] = None

            return result
        finally:
            await page.close()
            await context.close()
            browser_manager.release_page(context)


web_fetcher = WebFetcher()
