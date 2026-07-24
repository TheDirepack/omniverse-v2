# ruff: noqa: ARG002, TRY003, RUF012

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

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
async def test_browser_adapter_is_lazy_bounded_and_closes_request_context() -> None:
    active = 0
    maximum = 0
    contexts = []

    class Page:
        url = "https://safe.test/final"

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

    class Context:
        closed = False

        async def new_page(self):
            return Page()

        async def close(self):
            self.closed = True

    class Browser:
        closed = False

        async def new_context(self):
            value = Context()
            contexts.append(value)
            return value

        async def close(self):
            self.closed = True

    launches = []
    browser = Browser()

    async def launch(**kwargs):
        launches.append(kwargs)
        return browser

    adapter = BrowserAcquisition(launcher=launch, resolver=Resolver(), concurrency=1)
    policy = AcquisitionPolicy(max_body_bytes=100, timeout_seconds=1)
    results = await asyncio.gather(
        adapter.acquire("https://start.test/a", policy),
        adapter.acquire("https://start.test/b", policy),
    )
    assert len(launches) == 1
    assert maximum == 1
    assert all(result.final_url == "https://safe.test/final" for result in results)
    assert all(context.closed for context in contexts)
    await adapter.close()
    assert browser.closed


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

    class Browser:
        async def new_context(self):
            return Context()

    async def launch(**_kwargs):
        return Browser()

    adapter = BrowserAcquisition(launcher=launch, resolver=Resolver())
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

    class Browser:
        async def new_context(self):
            return Context()

    async def launch(**_kwargs):
        return Browser()

    adapter = BrowserAcquisition(launcher=launch, resolver=Resolver())
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
