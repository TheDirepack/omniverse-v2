import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import socket
from app.core.browser import browser_manager

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
    async def fetch_page(self, url: str, include_freshness: bool = True) -> str:
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
                # Some pages (analytics beacons, live chat widgets, etc.) never go
                # fully idle. Fall back to a looser wait rather than failing the
                # whole fetch — partial/late-loading content is still useful.
                response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
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
            for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript", "header"]):
                tag.decompose()
            text = "\n".join(line.strip() for line in soup.get_text().splitlines() if line.strip())

            if len(text) > 20000:
                text = text[:20000] + "\n... [truncated at 20,000 characters]"

            if not include_freshness:
                return text

            signals = _extract_freshness_signals(url, final_url, html, text, last_modified_header)
            return signals + "\n" + text
        finally:
            await page.close()
            await context.close()
            browser_manager.release_page(context)


web_fetcher = WebFetcher()
