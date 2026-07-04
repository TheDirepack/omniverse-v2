from bs4 import BeautifulSoup
from urllib.parse import urlparse
import socket
from app.core.browser import browser_manager

class WebFetcher:
    async def fetch_page(self, url: str) -> str:
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
