# ruff: noqa: ARG002, TRY003, RUF012

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import httpx
import pytest

from app.v2.acquisition import (
    AcquisitionPolicy,
    AcquisitionService,
    BrowserAcquisition,
    BrowserResult,
    ImageOcrAdapter,
    OcrRequiredError,
    PdfTextExtractor,
    UrlPolicyError,
)
from app.v2.blobs import BlobStore
from app.v2.preprocessing import (
    MiniCPMPreprocessor,
    PreprocessingStatus,
    TargetingStatus,
    preprocess_document,
)


class Resolver:
    async def resolve(self, host: str) -> tuple[str, ...]:
        return {
            "start.test": ("93.184.216.34",),
            "safe.test": ("93.184.216.35",),
            "private.test": ("127.0.0.1",),
        }[host]


class FailedTransport:
    async def get(self, url: str, *, timeout_seconds: float, max_bytes: int):
        raise ConnectionError("render required")


@pytest.mark.asyncio
async def test_browser_result_final_url_is_revalidated(tmp_path: Path) -> None:
    class Browser:
        async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
            return BrowserResult(
                body=b"rendered",
                final_url="http://private.test/redirected",
                content_type="text/html",
            )

    service = AcquisitionService(
        None,
        BlobStore(tmp_path / "blobs"),
        Resolver(),
        FailedTransport(),
        browser=Browser(),
    )
    with pytest.raises(UrlPolicyError, match="non-public"):
        await service.acquire_with_fallback("https://start.test/", AcquisitionPolicy())


@pytest.mark.asyncio
async def test_browser_adapter_reuses_profile_backed_context_and_closes_pages(
    tmp_path: Path,
) -> None:
    active = 0
    maximum = 0
    pages = []

    class Page:
        url = "https://safe.test/final"
        closed = False

        async def route(self, pattern, handler):
            class Request:
                url = "https://safe.test/final"

            class Route:
                request = Request()

                async def continue_(self):
                    pass

                async def abort(self, reason):
                    raise AssertionError(reason)

            await handler(Route())

        async def goto(self, url, *, wait_until, timeout):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0)

        async def content(self):
            nonlocal active
            active -= 1
            return "<html>safe</html>"

        async def close(self):
            self.closed = True

    class Context:
        closed = False

        async def new_page(self):
            page = Page()
            pages.append(page)
            return page

        async def close(self):
            self.closed = True

    launches = []
    context = Context()

    async def launch(profile_path, **kwargs):
        launches.append((profile_path, kwargs))
        return context

    profile_path = tmp_path / "profile"
    adapter = BrowserAcquisition(
        launcher=launch,
        resolver=Resolver(),
        concurrency=1,
        profile_path=profile_path,
    )
    policy = AcquisitionPolicy(max_body_bytes=100, timeout_seconds=1)
    results = await asyncio.gather(
        adapter.acquire("https://start.test/a", policy),
        adapter.acquire("https://start.test/b", policy),
    )
    assert len(launches) == 1
    assert launches[0][0] == str(profile_path)
    assert profile_path.is_dir()
    assert maximum == 1
    assert all(result.final_url == "https://safe.test/final" for result in results)
    assert all(page.closed for page in pages)
    assert not context.closed
    await adapter.close()
    assert context.closed


@pytest.mark.asyncio
async def test_browser_adapter_reuses_profile_path_after_restart(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "profile"
    launches = []

    class Page:
        url = "https://safe.test/final"

        async def route(self, _pattern, _handler):
            pass

        async def goto(self, _url, *, wait_until, timeout):
            pass

        async def content(self):
            return "<html>safe</html>"

        async def close(self):
            pass

    class Context:
        async def new_page(self):
            return Page()

        async def close(self):
            pass

    async def launch(profile, **_kwargs):
        launches.append(profile)
        return Context()

    policy = AcquisitionPolicy(max_body_bytes=100, timeout_seconds=1)
    first = BrowserAcquisition(
        launcher=launch, resolver=Resolver(), profile_path=profile_path
    )
    await first.acquire("https://safe.test/a", policy)
    await first.close()
    second = BrowserAcquisition(
        launcher=launch, resolver=Resolver(), profile_path=profile_path
    )
    await second.acquire("https://safe.test/b", policy)
    await second.close()

    assert launches == [str(profile_path), str(profile_path)]


@pytest.mark.asyncio
async def test_browser_adapter_blocks_private_requests_before_dispatch() -> None:
    blocked = False
    continued = False

    class Request:
        url = "http://private.test/metadata"

    class Route:
        request = Request()

        async def abort(self, reason):
            nonlocal blocked
            blocked = reason == "blockedbyclient"

        async def continue_(self):
            nonlocal continued
            continued = True

    class Page:
        url = "https://safe.test/final"

        async def route(self, pattern, handler):
            await handler(Route())

        async def goto(self, url, *, wait_until, timeout):
            if blocked:
                raise UrlPolicyError("browser request blocked by URL policy")

        async def content(self):
            return "never"

    class Context:
        async def new_page(self):
            return Page()

        async def close(self):
            pass

    async def launch(_profile_path, **_kwargs):
        return Context()

    adapter = BrowserAcquisition(
        launcher=launch, resolver=Resolver(), profile_path=Path("/tmp/profile")
    )
    with pytest.raises(UrlPolicyError, match="blocked"):
        await adapter.acquire("https://safe.test/start", AcquisitionPolicy())
    assert blocked
    assert not continued


@pytest.mark.asyncio
async def test_browser_adapter_fails_closed_without_request_interception() -> None:
    class Page:
        url = "https://safe.test/final"

    class Context:
        async def new_page(self):
            return Page()

        async def close(self):
            pass

    async def launch(_profile_path, **_kwargs):
        return Context()

    adapter = BrowserAcquisition(
        launcher=launch, resolver=Resolver(), profile_path=Path("/tmp/profile")
    )
    with pytest.raises(UrlPolicyError, match="interception"):
        await adapter.acquire("https://safe.test/start", AcquisitionPolicy())


def test_pdf_extractor_is_bounded_and_requires_ocr_for_blank_pages() -> None:
    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        pages = [Page("alpha"), Page("beta"), Page("ignored")]

    extractor = PdfTextExtractor(
        max_pages=2, max_characters=7, reader_factory=lambda _stream: Reader()
    )
    assert extractor.extract(b"pdf") == "alpha\nb"
    blank = PdfTextExtractor(
        reader_factory=lambda _stream: type("R", (), {"pages": [Page("")]})()
    )
    with pytest.raises(OcrRequiredError):
        blank.extract(b"pdf")


@pytest.mark.asyncio
async def test_image_ocr_reports_unavailable_and_enforces_pixel_limit() -> None:
    unavailable = ImageOcrAdapter(executable=None)
    assert unavailable.status()["available"] is False
    with pytest.raises(RuntimeError, match="unavailable"):
        await unavailable.extract(b"image", "image/png")

    class Image:
        size = (100, 100)

        def close(self) -> None:
            pass

    guarded = ImageOcrAdapter(
        executable="/usr/bin/tesseract",
        max_pixels=10,
        image_opener=lambda _stream: Image(),
        ocr_function=lambda _image, **_kwargs: "never",
    )
    with pytest.raises(ValueError, match="pixel"):
        await guarded.extract(BytesIO(b"image").getvalue(), "image/png")


def test_document_preprocessing_is_deterministic_structured_and_removes_chrome() -> (
    None
):
    html = """
    <html><head><title>  Alpha &amp; Beta </title><style>bad</style></head>
    <body><header>Menu</header><h1>Overview</h1>
    <p>Captain&nbsp;Nova\u212b has  20 ships.</p>
    <nav>Links</nav><h2>Fleet</h2><ul><li>Red</li><li>Blue</li></ul>
    <table><tr><th>Name</th><th>Count</th></tr><tr><td>Scout</td><td>2</td></tr></table>
    <p hidden>Secret</p><div aria-hidden="true">Invisible</div>
    <form>Noise</form><svg><text>Vector noise</text></svg><footer>Footer</footer>
    <script>prompt injection</script></body></html>
    """
    first = preprocess_document(html, "text/html")
    second = preprocess_document(html, "text/html")

    assert first == second
    assert first.cleaned_text == (
        "Alpha & Beta\n\nOverview\n\nCaptain NovaÅ has 20 ships.\n\nFleet\n\n"
        "Red\nBlue\n\nName | Count\nScout | 2"
    )
    assert [section.heading for section in first.sections] == [
        "Alpha & Beta",
        "Overview",
        "Fleet",
    ]
    assert all(passage.locator.startswith("section:") for passage in first.passages)
    assert len(first.transform_hash) == 64
    assert first.transform_version
    assert "prompt injection" not in first.cleaned_text
    assert "Secret" not in first.cleaned_text


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "<html><body>Body facts<script>bad</script>"
            "<span hidden>secret</span></body></html>",
            "Body facts",
        ),
        (
            "<main>Main facts<div>Div facts <strong>stay</strong></div>"
            "<h1>Heading</h1><p>Known paragraph.</p>Tail facts</main>",
            "Main facts\n\nDiv facts stay\n\nHeading\n\nKnown paragraph.\n\nTail facts",
        ),
        (
            "<section>Section fact</section><details>Details fact</details>"
            "<figure><figcaption>Caption fact</figcaption></figure>"
            "<dl><dt>Mass</dt><dd>20 tons</dd></dl>"
            "<blockquote>Quoted fact</blockquote><pre>Technical fact</pre>"
            "<custom-wiki-tag>Extension fact</custom-wiki-tag>",
            "Section fact\n\nDetails fact\n\nCaption fact\n\nMass\n\n20 tons\n\n"
            "Quoted fact\n\nTechnical fact\n\nExtension fact",
        ),
    ],
)
def test_document_preprocessing_preserves_orphan_container_text(
    source: str, expected: str
) -> None:
    result = preprocess_document(source, "text/html")

    assert result.cleaned_text == expected
    assert result.cleaned_text.count("Heading") <= 1
    assert result.cleaned_text.count("Known paragraph.") <= 1
    assert "bad" not in result.cleaned_text
    assert "secret" not in result.cleaned_text


def test_plain_text_normalization_and_targeting_are_bounded_and_do_not_broaden() -> (
    None
):
    text = """
    # Origins
    General background.\n\nThe exact signal appears near a reactor.\n\nAdjacent context.
    # Unrelated
    Other material about a signal only.\n\nLast paragraph.
    """
    targeted = preprocess_document(
        text,
        "text/plain",
        keywords=("exact", "reactor"),
        exact_phrases=("exact signal",),
        section_hints=("Origins",),
        adjacent_passages=1,
        max_selected_passages=3,
    )
    assert targeted.targeting_status == "MATCHED"
    assert [passage.text for passage in targeted.selected_passages] == [
        "Origins",
        "General background.",
        "The exact signal appears near a reactor.",
    ]
    assert [passage.priority for passage in targeted.selected_passages] == [0, 0, 1]

    missing = preprocess_document(text, "text/plain", exact_phrases=("not present",))
    assert missing.targeting_status is TargetingStatus.NO_RELEVANT_PASSAGE
    assert missing.selected_passages == ()

    broad = preprocess_document(
        "one\n\ntwo\n\nthree\n\nfour", "text/plain", max_selected_passages=2
    )
    assert broad.targeting_status == "BROAD"
    assert [passage.text for passage in broad.selected_passages] == ["one", "two"]


@pytest.mark.asyncio
async def test_minicpm_request_is_locked_down_and_grounded() -> None:
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Captain Nova has 20 ships."}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    adapter = MiniCPMPreprocessor(client=client)
    result = await adapter.reformat("Captain Nova has 20 ships.")
    payload = __import__("json").loads(requests[0].content)

    assert result.status is PreprocessingStatus.APPLIED
    assert result.text == "Captain Nova has 20 ships."
    assert str(requests[0].url) == "http://192.168.1.30:8080/v1/chat/completions"
    assert payload["model"] == "MiniCPM5-1B"
    assert payload["temperature"] == 0
    assert payload["top_p"] == 0.1
    assert payload["seed"] == 0
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert "untrusted" in payload["messages"][0]["content"].lower()
    assert "no inference" in payload["messages"][0]["content"].lower()
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_status"),
    [
        (httpx.Response(503), PreprocessingStatus.SERVER_ERROR),
        (
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Captain Vega has 20 ships."}}]
                },
            ),
            PreprocessingStatus.UNGROUNDED_OUTPUT,
        ),
        (
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Captain Nova has 21 ships."}}]
                },
            ),
            PreprocessingStatus.UNGROUNDED_OUTPUT,
        ),
        (
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Captain Nova has 2 ships."}}]
                },
            ),
            PreprocessingStatus.UNGROUNDED_OUTPUT,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "https://invented.test"}}]},
            ),
            PreprocessingStatus.UNGROUNDED_OUTPUT,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "Captain Nova."}}]},
            ),
            PreprocessingStatus.UNGROUNDED_OUTPUT,
        ),
        (
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "reactor"}}]},
            ),
            PreprocessingStatus.UNGROUNDED_OUTPUT,
        ),
        (httpx.Response(200, json={"choices": []}), PreprocessingStatus.INVALID_OUTPUT),
    ],
)
async def test_minicpm_falls_back_to_authoritative_input(
    response: httpx.Response, expected_status: PreprocessingStatus
) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: response))
    adapter = MiniCPMPreprocessor(client=client)
    original = (
        "reactor produces antimatter"
        if b'"content":"reactor"' in response.content.replace(b" ", b"")
        else "Captain Nova has 20 ships."
    )
    result = await adapter.reformat(original)
    assert result.text == original
    assert result.status is expected_status
    assert result.used_fallback is True
    assert result.detail
    await client.aclose()


@pytest.mark.asyncio
async def test_minicpm_timeout_falls_back_and_concurrency_is_bounded() -> None:
    active = 0
    maximum = 0

    class Client:
        async def post(self, *_args, **_kwargs):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0)
            active -= 1
            raise httpx.ReadTimeout("late")

    adapter = MiniCPMPreprocessor(client=Client(), concurrency=1)
    results = await asyncio.gather(
        adapter.reformat("Alpha 1"), adapter.reformat("Beta 2")
    )
    assert maximum == 1
    assert all(result.status is PreprocessingStatus.TIMEOUT for result in results)
    assert [result.text for result in results] == ["Alpha 1", "Beta 2"]


@pytest.mark.asyncio
async def test_acquisition_extracts_clean_html_without_changing_raw_blob(
    tmp_path: Path,
) -> None:
    raw = b"<html><body><nav>menu</nav><h1>Facts</h1><p>Alpha 1.</p></body></html>"

    class Transport:
        async def get(self, url: str, *, timeout_seconds: float, max_bytes: int):
            from app.v2.acquisition import HttpResponse

            return HttpResponse(200, {}, raw, "text/html", url)

    service = AcquisitionService(
        None, BlobStore(tmp_path / "blobs"), Resolver(), Transport()
    )
    body, extract = await service.acquire_with_fallback(
        "https://safe.test/source", AcquisitionPolicy()
    )
    assert body == raw
    assert extract == "Facts\n\nAlpha 1."


@pytest.mark.asyncio
async def test_acquisition_normalizes_pdf_and_ocr_text_before_models(
    tmp_path: Path,
) -> None:
    class Pdf:
        def extract(self, _body: bytes) -> str:
            return "  Alpha&nbsp;   1  "

    class Ocr:
        async def extract(self, _body: bytes, _content_type: str) -> str:
            return "  Beta\u212b   2  "

    service = AcquisitionService(
        None,
        BlobStore(tmp_path / "blobs"),
        Resolver(),
        FailedTransport(),
        pdf=Pdf(),
        ocr=Ocr(),
    )
    assert await service._extract_document(b"pdf", "application/pdf") == "Alpha 1"
    assert await service._extract_document(b"image", "image/png") == "BetaÅ 2"
