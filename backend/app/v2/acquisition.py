# Boundary errors intentionally carry stable policy diagnostics.
# ruff: noqa: SIM105, TRY003

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import socket
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from shutil import which
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.v2.blobs import BlobStore
from app.v2.logging import redact
from app.v2.models import AcquisitionCache, Source, SourceRevision, ToolEvent
from app.v2.preprocessing import PreprocessingStatus, preprocess_document


class UrlPolicyError(ValueError):
    pass


class NonSuccessResponseError(UrlPolicyError):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP response status {status} is not successful")
        self.status = status


@dataclass(frozen=True, slots=True)
class AcquisitionPolicy:
    max_redirects: int = 4
    max_body_bytes: int = 5_000_000
    timeout_seconds: float = 15.0
    allowed_content_types: tuple[str, ...] = (
        "text/plain",
        "text/html",
        "application/xhtml+xml",
        "application/json",
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/webp",
    )
    freshness_seconds: int = 3_600
    allow_private: bool = False


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    content_type: str
    final_url: str
    elapsed_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class BrowserResult:
    body: bytes
    final_url: str
    content_type: str = "text/html"


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    source_id: str
    revision_id: str
    canonical_url: str
    blob_hash: str
    extract: str
    cached: bool
    content_type: str = ""
    deterministic_blob_hash: str | None = None
    readability_blob_hash: str | None = None
    targeting_status: str = "BROAD"
    preprocessing_status: str = "DISABLED"
    authoritative_passages: tuple[dict[str, str], ...] = ()
    readability_text: str = ""


@dataclass(frozen=True, slots=True)
class LeadOnlyResult:
    url: str
    snippet: str
    support_role: str = "LEAD_ONLY"
    can_be_evidence: bool = False

    @classmethod
    def from_search(cls, url: str, snippet: str) -> LeadOnlyResult:
        return cls(url=canonicalize_url(url), snippet=snippet)


class Resolver(Protocol):
    async def resolve(self, host: str) -> tuple[str, ...]: ...


class HttpTransport(Protocol):
    async def get(
        self, url: str, *, timeout_seconds: float, max_bytes: int
    ) -> HttpResponse: ...


class BrowserFallback(Protocol):
    async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult: ...

    async def close(self) -> None: ...


class OcrFallback(Protocol):
    async def extract(self, body: bytes, content_type: str) -> str: ...

    def status(self) -> dict[str, object]: ...

    async def close(self) -> None: ...


class PdfFallback(Protocol):
    def extract(self, body: bytes) -> str: ...

    def status(self) -> dict[str, object]: ...

    async def close(self) -> None: ...


class OcrRequiredError(ValueError):
    pass


class UnsupportedExtractionError(ValueError):
    pass


class BrowserAcquisition:
    def __init__(
        self,
        *,
        launcher=None,
        resolver: Resolver | None = None,
        concurrency: int = 2,
        headless: bool = True,
        profile_path: Path | None = None,
    ) -> None:
        self._launcher = launcher
        self._resolver = resolver or ProductionResolver()
        self._headless = headless
        self._profile_path = profile_path or (
            Path(__file__).resolve().parents[2]
            / "data"
            / "v2-secrets"
            / "browser-profile"
        )
        self._semaphore = asyncio.Semaphore(concurrency)
        self._launch_lock = asyncio.Lock()
        self._context = None

    def status(self) -> dict[str, object]:
        return {"available": True, "detail": "lazy; not launched"}

    async def _get_context(self):
        if self._context is not None:
            return self._context
        async with self._launch_lock:
            if self._context is None:
                await asyncio.to_thread(
                    self._profile_path.mkdir, mode=0o700, parents=True, exist_ok=True
                )
                launcher = self._launcher
                if launcher is None:
                    from cloakbrowser import launch_persistent_context_async

                    launcher = launch_persistent_context_async
                self._context = await launcher(
                    str(self._profile_path), headless=self._headless
                )
        return self._context

    async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
        async with self._semaphore:
            context = await self._get_context()
            page = None
            try:
                page = await context.new_page()
                blocked_error: UrlPolicyError | None = None

                async def enforce_request_policy(route) -> None:
                    nonlocal blocked_error
                    try:
                        await _validate_url(route.request.url, self._resolver, policy)
                    except UrlPolicyError as error:
                        blocked_error = error
                        await route.abort("blockedbyclient")
                        return
                    await route.continue_()

                if not hasattr(page, "route"):
                    raise UrlPolicyError("browser request interception is unavailable")
                await page.route("**/*", enforce_request_policy)
                try:
                    await asyncio.wait_for(
                        page.goto(
                            url,
                            wait_until="domcontentloaded",
                            timeout=int(policy.timeout_seconds * 1_000),
                        ),
                        timeout=policy.timeout_seconds,
                    )
                except Exception:
                    if blocked_error is not None:
                        raise UrlPolicyError(
                            "browser request blocked by URL policy"
                        ) from blocked_error
                    raise
                if blocked_error is not None:
                    raise UrlPolicyError(
                        "browser request blocked by URL policy"
                    ) from blocked_error
                html = await asyncio.wait_for(
                    page.content(), timeout=policy.timeout_seconds
                )
                body = html.encode("utf-8")
                if len(body) > policy.max_body_bytes:
                    raise UrlPolicyError("browser body exceeds policy")
                return BrowserResult(body, str(page.url), "text/html")
            finally:
                if page is not None:
                    with suppress(Exception):
                        await page.close()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None


class PdfTextExtractor:
    def __init__(
        self,
        *,
        max_pages: int = 100,
        max_characters: int = 200_000,
        reader_factory=None,
    ) -> None:
        self.max_pages = max_pages
        self.max_characters = max_characters
        self._reader_factory = reader_factory

    def status(self) -> dict[str, object]:
        return {"available": True, "detail": "pypdf text extraction"}

    def extract(self, body: bytes) -> str:
        factory = self._reader_factory
        if factory is None:
            from pypdf import PdfReader

            factory = PdfReader
        reader = factory(BytesIO(body))
        pieces: list[str] = []
        remaining = self.max_characters
        for page in reader.pages[: self.max_pages]:
            if remaining <= 0:
                break
            text = (page.extract_text() or "").strip()
            if text:
                addition = text[:remaining]
                pieces.append(addition)
                remaining -= len(addition) + (1 if pieces else 0)
        result = "\n".join(pieces)[: self.max_characters]
        if not result.strip():
            raise OcrRequiredError("PDF contains no extractable text; OCR required")
        return result

    async def close(self) -> None:
        return None


class ImageOcrAdapter:
    def __init__(
        self,
        *,
        executable: str | None | object = ...,
        max_bytes: int = 10_000_000,
        max_pixels: int = 25_000_000,
        timeout_seconds: float = 15.0,
        image_opener=None,
        ocr_function=None,
    ) -> None:
        self.executable = which("tesseract") if executable is ... else executable
        self.max_bytes = max_bytes
        self.max_pixels = max_pixels
        self.timeout_seconds = timeout_seconds
        self._image_opener = image_opener
        self._ocr_function = ocr_function

    def status(self) -> dict[str, object]:
        return {
            "available": self.executable is not None,
            "detail": (
                f"tesseract at {self.executable}"
                if self.executable is not None
                else "tesseract executable unavailable"
            ),
        }

    async def extract(self, body: bytes, content_type: str) -> str:
        if self.executable is None:
            raise RuntimeError("image OCR unavailable")
        if not content_type.split(";", 1)[0].lower().startswith("image/"):
            raise UnsupportedExtractionError("OCR adapter only accepts images")
        if len(body) > self.max_bytes:
            raise ValueError("OCR input exceeds byte limit")

        def run() -> str:
            opener = self._image_opener
            ocr = self._ocr_function
            if opener is None or ocr is None:
                import pytesseract
                from PIL import Image

                opener = Image.open
                ocr = pytesseract.image_to_string
            image = opener(BytesIO(body))
            try:
                width, height = image.size
                if width * height > self.max_pixels:
                    raise ValueError("OCR image exceeds pixel limit")
                return str(ocr(image, config="--psm 6")).strip()
            finally:
                image.close()

        return await asyncio.wait_for(
            asyncio.to_thread(run), timeout=self.timeout_seconds
        )

    async def close(self) -> None:
        return None


class ProductionResolver:
    async def resolve(self, host: str) -> tuple[str, ...]:
        loop = asyncio.get_running_loop()
        values = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return tuple(sorted({str(value[4][0]) for value in values}))


class HttpxTransport:
    """Bounded transport. DNS is revalidated before each hop by AcquisitionService.

    httpx resolves again when connecting, so DNS rebinding cannot be completely pinned
    without a custom network backend. Deployment egress controls remain the final SSRF
    boundary; every requested and redirected hostname is nevertheless checked here.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def get(
        self, url: str, *, timeout_seconds: float, max_bytes: int
    ) -> HttpResponse:
        try:
            return await asyncio.wait_for(
                self._get(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes),
                timeout=timeout_seconds,
            )
        except TimeoutError as error:
            raise TimeoutError("HTTP request exceeded total deadline") from error

    async def _get(
        self, url: str, *, timeout_seconds: float, max_bytes: int
    ) -> HttpResponse:
        started = __import__("time").monotonic()
        try:
            async with self.client.stream(
                "GET", url, follow_redirects=False, timeout=timeout_seconds
            ) as response:
                if response.status_code >= 400:
                    raise NonSuccessResponseError(response.status_code)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise UrlPolicyError("response body exceeds policy")
                return HttpResponse(
                    status=response.status_code,
                    headers=dict(response.headers),
                    body=bytes(body),
                    content_type=response.headers.get("content-type", ""),
                    final_url=str(response.url),
                    elapsed_seconds=__import__("time").monotonic() - started,
                )
        except httpx.TimeoutException as error:
            raise TimeoutError("HTTP request timed out") from error
        except httpx.NetworkError as error:
            raise ConnectionError("HTTP network failure") from error


def canonicalize_url(url: str) -> str:
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if (
        scheme not in {"http", "https"}
        or not host
        or parsed.username
        or parsed.password
    ):
        raise UrlPolicyError(
            "URL must be an absolute http/https URL without credentials"
        )
    port = parsed.port
    netloc = host
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def _policy_hash(policy: AcquisitionPolicy) -> str:
    encoded = json.dumps(asdict(policy), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _validate_url(url: str, resolver: Resolver, policy: AcquisitionPolicy) -> str:
    canonical = canonicalize_url(url)
    host = urlsplit(canonical).hostname
    assert host is not None
    addresses = await resolver.resolve(host)
    if not addresses:
        raise UrlPolicyError("host did not resolve")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as error:
            raise UrlPolicyError("resolver returned an invalid address") from error
        if not policy.allow_private and not ip.is_global:
            raise UrlPolicyError("URL resolves to a non-public address")
    return canonical


class AcquisitionService:
    def __init__(
        self,
        engine,
        blobs: BlobStore,
        resolver: Resolver,
        transport: HttpTransport,
        *,
        browser: BrowserFallback | None = None,
        ocr: OcrFallback | None = None,
        pdf: PdfFallback | None = None,
        preprocessor: Any | None = None,
        clock=None,
        logger=None,
    ) -> None:
        self.engine = engine
        self.blobs = blobs
        self.resolver = resolver
        self.transport = transport
        self.browser = browser
        self.ocr = ocr
        self.pdf = pdf
        self.preprocessor = preprocessor
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.logger = logger

    def _log(
        self, event_type: str, message: str, *, level="INFO", data=None, **correlation
    ) -> None:
        if self.logger is None:
            return
        try:
            self.logger.log_agent(
                "acquisition",
                event_type,
                message=message,
                level=level,
                data=redact(
                    {
                        **{
                            name: correlation[name]
                            for name in ("attempt_number", "step_kind")
                            if correlation.get(name) is not None
                        },
                        **(data or {}),
                    }
                ),
                **correlation,
            )
        except Exception:
            pass

    async def validate_url(self, url: str, policy: AcquisitionPolicy) -> str:
        return await _validate_url(url, self.resolver, policy)

    async def fetch_http(
        self, url: str, policy: AcquisitionPolicy
    ) -> tuple[str, HttpResponse]:
        current = await self.validate_url(url, policy)
        for redirect_count in range(policy.max_redirects + 1):
            started = monotonic()
            data = {
                "url": current,
                "redirect_count": redirect_count,
                "max_bytes": policy.max_body_bytes,
            }
            self._log(
                "acquisition.http.started",
                "Acquisition HTTP request started",
                data=data,
            )
            try:
                response = await self.transport.get(
                    current,
                    timeout_seconds=policy.timeout_seconds,
                    max_bytes=policy.max_body_bytes,
                )
            except Exception as error:
                self._log(
                    "acquisition.http.failed",
                    "Acquisition HTTP request failed",
                    level="ERROR",
                    data={
                        **data,
                        "duration_ms": (monotonic() - started) * 1000,
                        "error_class": type(error).__name__,
                        "error_message": str(error),
                    },
                )
                raise
            response_data = {
                **data,
                "duration_ms": (monotonic() - started) * 1000,
                "status": response.status,
                "content_type": response.content_type,
                "body_length": len(response.body),
                "body_sha256": hashlib.sha256(response.body).hexdigest(),
            }
            if 300 <= response.status < 400:
                location = response.headers.get("location") or response.headers.get(
                    "Location"
                )
                if not location:
                    raise UrlPolicyError("redirect missing location")
                if redirect_count >= policy.max_redirects:
                    raise UrlPolicyError("redirect limit exceeded")
                current = await self.validate_url(urljoin(current, location), policy)
                continue
            if not 200 <= response.status < 300:
                self._log(
                    "acquisition.http.failed",
                    "Acquisition HTTP response rejected",
                    level="ERROR",
                    data={**response_data, "error_class": "NonSuccessResponseError"},
                )
                raise NonSuccessResponseError(response.status)
            if len(response.body) > policy.max_body_bytes:
                raise UrlPolicyError("response body exceeds policy")
            content_type = response.content_type.split(";", 1)[0].lower()
            if content_type not in policy.allowed_content_types:
                raise UrlPolicyError("content type is not allowed")
            self._log(
                "acquisition.http.succeeded",
                "Acquisition HTTP request succeeded",
                data=response_data,
            )
            return current, response
        raise UrlPolicyError("redirect limit exceeded")

    async def acquire_with_fallback(
        self, url: str, policy: AcquisitionPolicy
    ) -> tuple[bytes, str]:
        try:
            _final_url, response = await self.fetch_http(url, policy)
            body = response.body
            content_type = response.content_type
        except UrlPolicyError:
            raise
        except (
            ConnectionError,
            IndexError,
            OSError,
            RuntimeError,
            TimeoutError,
        ) as error:
            if self.browser is None:
                raise
            canonical = await self.validate_url(url, policy)
            rendered = await self.browser.acquire(canonical, policy)
            await self.validate_url(rendered.final_url, policy)
            body = rendered.body
            if len(body) > policy.max_body_bytes:
                raise UrlPolicyError("browser body exceeds policy") from error
            content_type = rendered.content_type
        extract = await self._extract_document(body, content_type)
        fallback = body.decode("utf-8", errors="replace")[:4_000]
        return body, extract[:4_000] if extract else fallback

    async def _extract_document(self, body: bytes, content_type: str) -> str:
        normalized = content_type.split(";", 1)[0].lower()
        if normalized == "application/pdf":
            if self.pdf is None:
                raise UnsupportedExtractionError("PDF extraction unavailable")
            extracted = await asyncio.to_thread(self.pdf.extract, body)
            return preprocess_document(extracted, "text/plain").cleaned_text
        if normalized.startswith("image/"):
            if self.ocr is None:
                raise UnsupportedExtractionError("image OCR unavailable")
            extracted = await self.ocr.extract(body, normalized)
            return preprocess_document(extracted, "text/plain").cleaned_text
        return self._extract(body, normalized)

    @staticmethod
    def _extract(body: bytes, content_type: str) -> str:
        if content_type.startswith("text/") or content_type in {
            "application/json",
            "application/xhtml+xml",
        }:
            source = body.decode("utf-8", errors="replace")
            return preprocess_document(source, content_type).cleaned_text[:4_000]
        return ""

    @staticmethod
    def _cache_fresh(fetched_at: datetime, now: datetime, seconds: int) -> bool:
        if fetched_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return fetched_at + timedelta(seconds=seconds) > now

    def _result_from_revision(
        self, revision: SourceRevision, source: Source, *, cached: bool
    ) -> AcquisitionResult:
        metadata = revision.extraction_metadata_json
        deterministic = metadata.get("deterministic", {})
        minicpm = metadata.get("minicpm", {})
        return self._result_from_derivatives(
            revision,
            source,
            {
                "deterministic_blob_hash": deterministic.get("blob_hash"),
                "readability_blob_hash": minicpm.get("blob_hash"),
                "targeting_status": deterministic.get("targeting_status", "BROAD"),
                "preprocessing_status": minicpm.get("status", "DISABLED"),
            },
            cached=cached,
        )

    def _result_from_derivatives(
        self,
        revision: SourceRevision,
        source: Source,
        metadata: dict,
        *,
        cached: bool,
    ) -> AcquisitionResult:
        if not metadata.get("deterministic_blob_hash"):
            return self._result_from_revision_legacy(revision, source, cached=cached)
        blob_hash = revision.blob_hash or revision.content_hash
        authoritative_passages: tuple[dict[str, str], ...] = ()
        derivative_hash = metadata.get("deterministic_blob_hash")
        if derivative_hash:
            derivative = json.loads(self.blobs.get(str(derivative_hash)))
            authoritative_passages = tuple(derivative.get("selected_passages", ()))
        extract = "\n\n".join(item["text"] for item in authoritative_passages)
        readability_hash = metadata.get("readability_blob_hash")
        readability_text = (
            self.blobs.get(str(readability_hash)).decode("utf-8")
            if readability_hash
            else extract
        )
        return AcquisitionResult(
            source.id,
            revision.id,
            source.canonical_url,
            blob_hash,
            extract,
            cached,
            revision.content_type or "",
            str(derivative_hash) if derivative_hash else None,
            str(readability_hash) if readability_hash else None,
            str(metadata.get("targeting_status", "BROAD")),
            str(metadata.get("preprocessing_status", "DISABLED")),
            authoritative_passages,
            readability_text,
        )

    def _result_from_revision_legacy(
        self, revision: SourceRevision, source: Source, *, cached: bool
    ) -> AcquisitionResult:
        blob_hash = revision.blob_hash or revision.content_hash
        metadata = revision.extraction_metadata_json
        extract = str(metadata.get("normalized_extract") or "")
        return AcquisitionResult(
            source.id,
            revision.id,
            source.canonical_url,
            blob_hash,
            extract,
            cached,
            revision.content_type or "",
            None,
            None,
            "BROAD",
            "DISABLED",
            (),
            extract,
        )

    async def _source_text(self, body: bytes, content_type: str) -> tuple[str, str]:
        normalized = content_type.split(";", 1)[0].lower()
        if normalized == "application/pdf":
            if self.pdf is None:
                raise UnsupportedExtractionError("PDF extraction unavailable")
            started = monotonic()
            self._log(
                "acquisition.pdf.started",
                "PDF extraction started",
                data={
                    "input_length": len(body),
                    "input_sha256": hashlib.sha256(body).hexdigest(),
                },
            )
            try:
                text = await asyncio.to_thread(self.pdf.extract, body)
            except Exception as error:
                self._log(
                    "acquisition.pdf.failed",
                    "PDF extraction failed",
                    level="ERROR",
                    data={
                        "duration_ms": (monotonic() - started) * 1000,
                        "error_class": type(error).__name__,
                    },
                )
                raise
            self._log(
                "acquisition.pdf.succeeded",
                "PDF extraction succeeded",
                data={
                    "duration_ms": (monotonic() - started) * 1000,
                    "output_length": len(text),
                    "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
                },
            )
            return text, "text/plain"
        if normalized.startswith("image/"):
            if self.ocr is None:
                raise UnsupportedExtractionError("image OCR unavailable")
            started = monotonic()
            self._log(
                "acquisition.ocr.started",
                "OCR extraction started",
                data={
                    "content_type": normalized,
                    "input_length": len(body),
                    "input_sha256": hashlib.sha256(body).hexdigest(),
                },
            )
            try:
                text = await self.ocr.extract(body, normalized)
            except Exception as error:
                self._log(
                    "acquisition.ocr.failed",
                    "OCR extraction failed",
                    level="ERROR",
                    data={
                        "duration_ms": (monotonic() - started) * 1000,
                        "error_class": type(error).__name__,
                    },
                )
                raise
            self._log(
                "acquisition.ocr.succeeded",
                "OCR extraction succeeded",
                data={
                    "duration_ms": (monotonic() - started) * 1000,
                    "output_length": len(text),
                    "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
                },
            )
            return text, "text/plain"
        if normalized.startswith("text/") or normalized in {
            "application/json",
            "application/xhtml+xml",
        }:
            return body.decode("utf-8", errors="replace"), normalized
        return "", "text/plain"

    async def acquire(
        self,
        url: str,
        policy: AcquisitionPolicy,
        *,
        force_refresh: bool = False,
        idempotency_key: str,
        attempt_id: str | None = None,
        step_id: str | None = None,
        run_id: str | None = None,
        target_id: str | None = None,
        world_id: str | None = None,
        attempt_number: int | None = None,
        step_kind: str | None = None,
        source_class: str = "SECONDARY",
        publisher: str | None = None,
        lineage_id: str | None = None,
        keywords: tuple[str, ...] = (),
        exact_phrases: tuple[str, ...] = (),
        section_hints: tuple[str, ...] = (),
    ) -> AcquisitionResult:
        if self.engine is None:
            raise RuntimeError("acquisition persistence requires an engine")
        canonical = canonicalize_url(url)
        correlation = {
            "run_id": run_id,
            "target_id": target_id,
            "step_id": step_id,
            "world_id": world_id,
            "attempt_number": attempt_number,
            "step_kind": step_kind,
        }
        self._log(
            "acquisition.started",
            "Source acquisition started",
            data={
                "url": canonical,
                "force_refresh": force_refresh,
                "attempt_id": attempt_id,
            },
            **correlation,
        )
        event_key = (
            f"{idempotency_key}:attempt:{attempt_id}" if attempt_id else idempotency_key
        )
        policy_hash = _policy_hash(policy)
        targeting_hash = hashlib.sha256(
            json.dumps(
                {
                    "keywords": keywords,
                    "exact_phrases": exact_phrases,
                    "section_hints": section_hints,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        cache_key = hashlib.sha256(
            f"{canonical}\0{policy_hash}\0{targeting_hash}".encode()
        ).hexdigest()
        now = self.clock()
        self._log(
            "acquisition.cache.started",
            "Acquisition cache lookup started",
            data={"url": canonical, "cache_key": cache_key},
            **correlation,
        )
        with Session(self.engine) as session:
            prior_event = session.scalar(
                select(ToolEvent).where(ToolEvent.idempotency_key == event_key)
            )
            if prior_event is not None and prior_event.source_revision_id is not None:
                revision = session.get(SourceRevision, prior_event.source_revision_id)
                source = session.get(Source, revision.source_id)
                result = self._result_from_derivatives(
                    revision,
                    source,
                    prior_event.extract_json or {},
                    cached=True,
                )
                self._log(
                    "acquisition.cache.succeeded",
                    "Acquisition cache lookup succeeded",
                    data={
                        "url": canonical,
                        "cache_key": cache_key,
                        "hit": True,
                        "revision_id": result.revision_id,
                    },
                    **correlation,
                )
                self._log(
                    "acquisition.cache.hit",
                    "Acquisition idempotency cache hit",
                    data={"url": canonical, "revision_id": result.revision_id},
                    **correlation,
                )
                return result
            if prior_event is not None and prior_event.status == "FAILED":
                self._log(
                    "acquisition.cache.failed",
                    "Cached acquisition records a prior failure",
                    level="ERROR",
                    data={
                        "url": canonical,
                        "cache_key": cache_key,
                        "error_class": prior_event.error_class,
                    },
                    **correlation,
                )
                raise UrlPolicyError("previous idempotent acquisition failed")
            cached = session.get(AcquisitionCache, cache_key)
            if (
                cached is not None
                and not force_refresh
                and self._cache_fresh(cached.fetched_at, now, policy.freshness_seconds)
            ):
                revision = session.get(SourceRevision, cached.source_revision_id)
                source = session.get(Source, revision.source_id)
                result = self._result_from_derivatives(
                    revision,
                    source,
                    cached.result_json or {},
                    cached=True,
                )
                self._record_event(
                    session, event_key, canonical, policy_hash, result, step_id=step_id
                )
                session.commit()
                self._log(
                    "acquisition.cache.succeeded",
                    "Acquisition cache lookup succeeded",
                    data={
                        "url": canonical,
                        "cache_key": cache_key,
                        "hit": True,
                        "revision_id": result.revision_id,
                    },
                    **correlation,
                )
                self._log(
                    "acquisition.cache.hit",
                    "Acquisition freshness cache hit",
                    data={"url": canonical, "revision_id": result.revision_id},
                    **correlation,
                )
                return result

        self._log(
            "acquisition.cache.succeeded",
            "Acquisition cache lookup succeeded",
            data={"url": canonical, "cache_key": cache_key, "hit": False},
            **correlation,
        )

        try:
            final_url, response = await self.fetch_http(canonical, policy)
        except UrlPolicyError:
            self._record_failure(
                event_key, canonical, policy_hash, "URL_POLICY", step_id
            )
            raise
        except (
            ConnectionError,
            IndexError,
            OSError,
            RuntimeError,
            TimeoutError,
        ) as error:
            if self.browser is None:
                self._record_failure(
                    event_key,
                    canonical,
                    policy_hash,
                    "BROWSER_UNAVAILABLE",
                    step_id,
                )
                raise
            final_url = await self.validate_url(canonical, policy)
            self._log(
                "acquisition.browser.started",
                "Browser acquisition started",
                data={"url": final_url},
                **correlation,
            )
            try:
                rendered = await self.browser.acquire(final_url, policy)
                final_url = await self.validate_url(rendered.final_url, policy)
                body = rendered.body
            except Exception:
                self._log(
                    "acquisition.browser.failed",
                    "Browser acquisition failed",
                    level="ERROR",
                    data={"url": final_url},
                    **correlation,
                )
                self._record_failure(
                    event_key, canonical, policy_hash, "BROWSER_FAILED", step_id
                )
                raise
            self._log(
                "acquisition.browser.succeeded",
                "Browser acquisition succeeded",
                data={
                    "url": final_url,
                    "body_length": len(body),
                    "body_sha256": hashlib.sha256(body).hexdigest(),
                    "content_type": rendered.content_type,
                },
                **correlation,
            )
            if len(body) > policy.max_body_bytes:
                self._record_failure(
                    event_key, canonical, policy_hash, "BODY_LIMIT", step_id
                )
                raise UrlPolicyError("browser body exceeds policy") from error
            response = HttpResponse(
                status=200,
                headers={},
                body=body,
                content_type=rendered.content_type,
                final_url=final_url,
            )
        canonical = canonicalize_url(final_url)
        # The raw provenance parent is content-addressed before any transformation.
        blob_hash = self.blobs.put(response.body)
        content_hash = hashlib.sha256(response.body).hexdigest()
        source_text, preprocessing_content_type = await self._source_text(
            response.body, response.content_type
        )
        deterministic = preprocess_document(
            source_text,
            preprocessing_content_type,
            keywords=keywords,
            exact_phrases=exact_phrases,
            section_hints=section_hints,
        )
        self._log(
            "preprocessing.deterministic.completed",
            "Deterministic preprocessing completed",
            data={
                "input_length": len(source_text),
                "input_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
                "transform_hash": deterministic.transform_hash,
                "targeting_status": deterministic.targeting_status.value,
                "selected_locators": [
                    item.locator for item in deterministic.selected_passages
                ],
                "selected_passage_disposition": "AUTHORITATIVE_SOURCE_EXCERPTS",
            },
            **correlation,
        )
        authoritative_passages = tuple(
            {"locator": passage.locator, "text": passage.text}
            for passage in deterministic.selected_passages
        )
        authoritative_text = "\n\n".join(
            passage["text"] for passage in authoritative_passages
        )
        derivative_document = {
            "cleaned_text": deterministic.cleaned_text,
            "sections": [
                {
                    "locator": section.locator,
                    "heading": section.heading,
                    "passage_locators": list(section.passage_locators),
                }
                for section in deterministic.sections
            ],
            "passages": [
                {
                    "locator": passage.locator,
                    "text": passage.text,
                    "kind": passage.kind,
                    "section_index": passage.section_index,
                    "passage_index": passage.passage_index,
                }
                for passage in deterministic.passages
            ],
            "selected_passages": list(authoritative_passages),
        }
        derivative_bytes = json.dumps(
            derivative_document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        deterministic_blob_hash = self.blobs.put(derivative_bytes)

        if not authoritative_passages:
            readability_text = ""
            readability_blob_hash = None
            preprocessing_status = "NOT_RUN"
            preprocessing_detail = "no relevant deterministic passage"
            used_fallback = True
        elif self.preprocessor is None:
            readability_text = authoritative_text
            readability_blob_hash = self.blobs.put(readability_text.encode("utf-8"))
            preprocessing_status = PreprocessingStatus.DISABLED.value
            preprocessing_detail = "preprocessor not configured"
            used_fallback = True
        else:
            model_result = await self.preprocessor.reformat(authoritative_text)
            readability_text = model_result.text
            readability_blob_hash = self.blobs.put(readability_text.encode("utf-8"))
            preprocessing_status = model_result.status.value
            preprocessing_detail = model_result.detail
            used_fallback = model_result.used_fallback

        deterministic_metadata = {
            **deterministic.metadata(),
            "targeting": {
                "keywords": list(keywords),
                "exact_phrases": list(exact_phrases),
                "section_hints": list(section_hints),
            },
            "blob_hash": deterministic_blob_hash,
            "input_blob_hash": blob_hash,
            "output_sha256": hashlib.sha256(derivative_bytes).hexdigest(),
            "selected_passages": list(authoritative_passages),
        }
        minicpm_metadata = {
            "transform": "readability-reformat-v1",
            "model": getattr(self.preprocessor, "model", None),
            "input_blob_hash": deterministic_blob_hash,
            "input_sha256": hashlib.sha256(authoritative_text.encode()).hexdigest(),
            "blob_hash": readability_blob_hash,
            "output_sha256": (
                hashlib.sha256(readability_text.encode()).hexdigest()
                if readability_blob_hash
                else None
            ),
            "status": preprocessing_status,
            "detail": preprocessing_detail,
            "used_fallback": used_fallback,
            "trust": "UNTRUSTED_NON_EVIDENTIARY",
        }
        with Session(self.engine) as session, session.begin():
            source = session.scalar(
                select(Source).where(Source.canonical_url == canonical)
            )
            if source is None:
                source = Source(
                    id=f"source-{hashlib.sha256(canonical.encode()).hexdigest()[:24]}",
                    canonical_url=canonical,
                    source_class=source_class,
                    publisher=publisher,
                    lineage_id=lineage_id,
                )
                session.add(source)
                session.flush()
            revision = session.scalar(
                select(SourceRevision).where(
                    SourceRevision.source_id == source.id,
                    SourceRevision.content_hash == content_hash,
                )
            )
            if revision is None:
                revision = SourceRevision(
                    id=f"revision-{uuid4().hex}",
                    source_id=source.id,
                    content_hash=content_hash,
                    blob_hash=blob_hash,
                    retrieved_at=now,
                    status_code=response.status,
                    content_type=response.content_type.split(";", 1)[0].lower(),
                    extractor_name="omniverse-deterministic-preprocessor",
                    extractor_version=deterministic.transform_version,
                    extraction_metadata_json={
                        "raw_parent_blob_hash": blob_hash,
                        "deterministic": deterministic_metadata,
                        "minicpm": minicpm_metadata,
                        "http": {
                            "final_url": canonical,
                            "status": response.status,
                            "content_length": len(response.body),
                            "elapsed_seconds": response.elapsed_seconds,
                            "etag": response.headers.get("etag"),
                            "last_modified": response.headers.get("last-modified"),
                        },
                    },
                )
                session.add(revision)
                session.flush()
            cache = session.get(AcquisitionCache, cache_key)
            if cache is None:
                cache = AcquisitionCache(
                    cache_key=cache_key,
                    canonical_url=canonical,
                    policy_hash=policy_hash,
                    source_revision_id=revision.id,
                    result_json={},
                    fetched_at=now,
                )
                session.add(cache)
            else:
                cache.source_revision_id = revision.id
                cache.fetched_at = now
            result = AcquisitionResult(
                source.id,
                revision.id,
                canonical,
                blob_hash,
                authoritative_text,
                False,
                response.content_type.split(";", 1)[0].lower(),
                deterministic_blob_hash,
                readability_blob_hash,
                deterministic.targeting_status.value,
                preprocessing_status,
                authoritative_passages,
                readability_text,
            )
            cache.result_json = {
                "deterministic_blob_hash": result.deterministic_blob_hash,
                "readability_blob_hash": result.readability_blob_hash,
                "targeting_status": result.targeting_status,
                "preprocessing_status": result.preprocessing_status,
            }
            self._record_event(
                session, event_key, canonical, policy_hash, result, step_id=step_id
            )
            self._log(
                "acquisition.succeeded",
                "Source acquisition succeeded",
                data={
                    "url": canonical,
                    "revision_id": result.revision_id,
                    "blob_hash": result.blob_hash,
                    "content_type": result.content_type,
                    "cached": False,
                },
                **correlation,
            )
            return result

    @staticmethod
    def _record_event(
        session: Session,
        idempotency_key: str,
        canonical_url: str,
        policy_hash: str,
        result: AcquisitionResult,
        *,
        step_id: str | None = None,
    ) -> None:
        session.add(
            ToolEvent(
                id=f"tool-{uuid4().hex}",
                step_id=step_id,
                status="SUCCEEDED",
                input_json={"canonical_url": canonical_url, "policy_hash": policy_hash},
                blob_hash=result.blob_hash,
                source_revision_id=result.revision_id,
                extract_json={
                    "characters": len(result.extract),
                    "sha256": hashlib.sha256(result.extract.encode()).hexdigest(),
                    "targeting_status": result.targeting_status,
                    "preprocessing_status": result.preprocessing_status,
                    "deterministic_blob_hash": result.deterministic_blob_hash,
                    "readability_blob_hash": result.readability_blob_hash,
                },
                error_class=None,
                idempotency_key=idempotency_key,
            )
        )

    def _record_failure(
        self,
        idempotency_key: str,
        canonical_url: str,
        policy_hash: str,
        error_class: str,
        step_id: str | None = None,
    ) -> None:
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(ToolEvent).where(ToolEvent.idempotency_key == idempotency_key)
            )
            if existing is None:
                session.add(
                    ToolEvent(
                        id=f"tool-{uuid4().hex}",
                        step_id=step_id,
                        status="FAILED",
                        input_json={
                            "canonical_url": canonical_url,
                            "policy_hash": policy_hash,
                        },
                        blob_hash=None,
                        source_revision_id=None,
                        extract_json=None,
                        error_class=error_class,
                        idempotency_key=idempotency_key,
                    )
                )
