import pytest
from bs4 import BeautifulSoup

from app.core.web_fetch import WebFetcher


@pytest.fixture
def fetcher():
    return WebFetcher()


def test_extract_internal_links(fetcher):
    html = """
    <html>
        <body>
            <nav>
                <a href="/home">Home</a>
                <a href="/privacy">Privacy Policy</a>
            </nav>
            <main>
                <h2>Technical Specifications</h2>
                <p>The <a href="/fusion-engine">Fusion Engine</a> is key.
                   The <a href="/fusion-engine">Fusion Engine</a> provides power.</p>
                <p>Heat is managed by <a href="/heat-sink">Heat Sinks</a>.</p>
            </main>
            <div class="catlinks">
                <a href="/cat/mechs">Mechs Category</a>
            </div>
            <div class="footer">
                <a href="/about">About Us</a>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    # Test default (max 20)
    links = fetcher._extract_internal_links(soup, base_url="http://example.com")

    # Fusion Engine should be High value and have score 2, and section
    # "Technical Specifications"
    fusion_engine = next(
        (link for link in links if link["title"] == "Fusion Engine"), None
    )
    assert fusion_engine is not None
    assert fusion_engine["tier"] == "High"
    assert fusion_engine["score"] == 2
    assert "Technical Specifications" in fusion_engine["sections"]
    assert fusion_engine["url"] == "http://example.com/fusion-engine"

    # Heat Sink should be High value and score 1
    heat_sink = next((link for link in links if link["title"] == "Heat Sinks"), None)
    assert heat_sink is not None
    assert heat_sink["tier"] == "High"
    assert heat_sink["score"] == 1
    assert "Technical Specifications" in heat_sink["sections"]

    # Categories should be Medium value
    mechs_cat = next(
        (link for link in links if link["title"] == "Mechs Category"), None
    )
    assert mechs_cat is not None
    assert mechs_cat["tier"] == "Medium"

    # Junk links should be filtered
    assert not any(link["title"] == "Privacy Policy" for link in links)
    assert not any(link["title"] == "About Us" for link in links)


def test_extract_internal_links_max(fetcher):
    html = """
    <html>
        <body>
            <main>
                <a href="/1">Link 1</a>
                <a href="/2">Link 2</a>
                <a href="/3">Link 3</a>
            </main>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    # Test capping at 2
    links = fetcher._extract_internal_links(
        soup, base_url="http://example.com", max_links=2
    )
    assert len(links) == 2


def test_normalize_whitespace(fetcher):
    text = "Line 1\n\n\nLine 2\n\nLine 3  with   many    spaces"
    expected = "Line 1\n\nLine 2\n\nLine 3 with many spaces"
    assert fetcher._normalize_whitespace(text) == expected


def test_is_cookie_page_positive(fetcher):
    # Text dominated by cookie keywords
    text = (
        "We value your privacy. Please accept all cookies to continue. "
        "Manage cookies in settings. Your privacy choices matter."
    )
    assert fetcher._is_cookie_page(text) is True


def test_is_cookie_page_negative(fetcher):
    # Normal article text
    text = (
        "The BattleMech is a giant robot used in the Inner Sphere. "
        "It uses a fusion engine and neurohelmet."
    )
    assert fetcher._is_cookie_page(text) is False


def test_detect_page_type_article(fetcher):
    html = "<html><body><h1>Article</h1><p>Content</p></body></html>"
    text = "Article Content"
    assert fetcher._detect_page_type(html, text) == "ARTICLE"


def test_detect_page_type_captcha(fetcher):
    html = "<html><body>Verify you are human. Please solve the CAPTCHA.</body></html>"
    text = "Verify you are human. Please solve the CAPTCHA."
    assert fetcher._detect_page_type(html, text) == "CAPTCHA"


def test_detect_page_type_404(fetcher):
    html = "<html><body>404 Not Found</body></html>"
    text = "404 Not Found"
    assert fetcher._detect_page_type(html, text) == "404 NOT FOUND"


def test_detect_page_type_login(fetcher):
    html = (
        "<html><body>Login: <input name='username'>"
        "<input name='password'></body></html>"
    )
    text = "Login username password"
    assert fetcher._detect_page_type(html, text) == "LOGIN PAGE"


def test_detect_page_type_search(fetcher):
    html = "<html><body>Search results for 'Mech'</body></html>"
    text = "Search results for 'Mech'"
    assert fetcher._detect_page_type(html, text) == "SEARCH RESULTS"


def test_extract_text_from_soup_stripping(fetcher):
    html = """
    <html>
        <body>
            <nav>Home | About</nav>
            <div class="cookie-banner">Accept all cookies</div>
            <div id="gdpr-consent">Manage privacy</div>
            <main>
                <p>Main content here.</p>
                <script>console.log('hi')</script>
                <footer>Footer info</footer>
            </main>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    text = fetcher._extract_text_from_soup(soup)

    assert "Main content here." in text
    assert "Home | About" not in text
    assert "Accept all cookies" not in text
    assert "Manage privacy" not in text
    assert "Footer info" not in text
    assert "console.log" not in text


def test_extract_research_signals(fetcher):
    html = """
    <html>
        <body>
            <nav aria-label="Breadcrumb">Home > Robots > Mechs</nav>
            <h2>See Also</h2>
            <ul>
                <li>OmniMech</li>
                <li>IndustrialMech</li>
            </ul>
            <div class="catlinks">
                Categories: [Mechs, Inner Sphere]
            </div>
            <table class="infobox">
                <tr><td>Height</td><td>12m</td></tr>
                <tr><td>Weight</td><td>50 tons</td></tr>
                <tr><td>Pilot</td><td>Neural-linked</td></tr>
                <tr><td>Origin</td><td>Inner Sphere</td></tr>
                <tr><td>Role</td><td>Frontline Combat</td></tr>
            </table>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    signals = fetcher._extract_research_signals(soup)

    assert "--- See Also ---" in signals
    assert "OmniMech" in signals
    assert "IndustrialMech" in signals
    assert "--- Categories ---" in signals
    assert "Mechs, Inner Sphere" in signals
    assert "--- Breadcrumbs ---" in signals
    assert "Home > Robots > Mechs" in signals
    assert "--- Infobox Summary ---" in signals
    assert "Height" in signals
    assert "12m" in signals
