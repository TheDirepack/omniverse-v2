# Injected fake interfaces intentionally ignore selected protocol arguments.
# ruff: noqa: ARG002

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.v2.acquisition import (
    AcquisitionPolicy,
    AcquisitionService,
    BrowserResult,
    HttpResponse,
    LeadOnlyResult,
    NonSuccessResponseError,
    UrlPolicyError,
)
from app.v2.blobs import BlobIntegrityError, BlobStore
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.models import Source, SourceRevision, ToolEvent


def test_blob_deduplication_and_integrity(isolated_paths: dict[str, Path]) -> None:
    store = BlobStore(isolated_paths["blobs"])
    first = store.put(b"same")
    second = store.put(b"same")
    assert first == second
    assert store.get(first) == b"same"
    store.path_for(first).write_bytes(b"tampered")
    with pytest.raises(BlobIntegrityError):
        store.get(first)


class Resolver:
    def __init__(self, values: dict[str, tuple[str, ...]]) -> None:
        self.values = values

    async def resolve(self, host: str) -> tuple[str, ...]:
        return self.values[host]


class Transport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.calls = 0

    async def get(
        self, url: str, *, timeout_seconds: float, max_bytes: int
    ) -> HttpResponse:
        self.calls += 1
        return self.responses.pop(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.2", "169.254.1.1", "::1"])
async def test_url_policy_blocks_non_public_dns(address: str) -> None:
    service = AcquisitionService(
        None,
        BlobStore(Path("/tmp/opencode/unused-blobs")),
        Resolver({"bad.test": (address,)}),
        Transport([]),
    )
    with pytest.raises(UrlPolicyError):
        await service.validate_url("https://bad.test/a", AcquisitionPolicy())


@pytest.mark.asyncio
async def test_redirect_is_revalidated_and_all_dns_answers_must_be_public(
    tmp_path: Path,
) -> None:
    transport = Transport(
        [
            HttpResponse(
                302,
                {"location": "http://internal.test/x"},
                b"",
                "text/html",
                "http://public.test",
            )
        ]
    )
    service = AcquisitionService(
        None,
        BlobStore(tmp_path / "blobs"),
        Resolver(
            {
                "public.test": ("93.184.216.34",),
                "internal.test": ("93.184.216.34", "10.1.2.3"),
            }
        ),
        transport,
    )
    with pytest.raises(UrlPolicyError):
        await service.fetch_http("http://public.test", AcquisitionPolicy())


@pytest.mark.asyncio
async def test_non_success_source_response_is_rejected(tmp_path: Path) -> None:
    service = AcquisitionService(
        None,
        BlobStore(tmp_path / "blobs"),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport(
            [
                HttpResponse(
                    404, {}, b"not evidence", "text/plain", "https://example.test"
                )
            ]
        ),
    )
    with pytest.raises(NonSuccessResponseError):
        await service.fetch_http("https://example.test", AcquisitionPolicy())


def test_pdf_bytes_are_never_utf8_decoded(tmp_path: Path) -> None:
    service = AcquisitionService(
        None, BlobStore(tmp_path / "blobs"), Resolver({}), Transport([])
    )
    assert service._extract(b"%PDF-\xff\xfe", "application/pdf") == ""


@pytest.mark.asyncio
@pytest.mark.integration
async def test_source_revision_cache_force_refresh_and_compact_event(
    isolated_paths,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    transport = Transport(
        [
            HttpResponse(
                200, {}, b"alpha body", "text/plain", "https://example.test/a"
            ),
            HttpResponse(
                200, {}, b"alpha body", "text/plain", "https://example.test/a"
            ),
            HttpResponse(200, {}, b"beta body", "text/plain", "https://example.test/a"),
        ]
    )
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        transport,
        clock=lambda: now,
    )
    policy = AcquisitionPolicy(freshness_seconds=300)
    first = await service.acquire(
        "HTTPS://EXAMPLE.TEST:443/a#fragment", policy, idempotency_key="one"
    )
    cached = await service.acquire(
        "https://example.test/a", policy, idempotency_key="two"
    )
    assert cached.revision_id == first.revision_id
    assert transport.calls == 1
    unchanged = await service.acquire(
        "https://example.test/a", policy, force_refresh=True, idempotency_key="three"
    )
    assert unchanged.revision_id == first.revision_id
    changed = await service.acquire(
        "https://example.test/a", policy, force_refresh=True, idempotency_key="four"
    )
    assert changed.revision_id != first.revision_id
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SourceRevision)) == 2
        event = session.scalar(
            select(ToolEvent).where(ToolEvent.idempotency_key == "four")
        )
        serialized = str(event.input_json) + str(event.extract_json)
        assert event.blob_hash == changed.blob_hash
        assert "beta body" not in serialized
        assert event.status == "SUCCEEDED"
        revision = session.get(SourceRevision, changed.revision_id)
        assert revision.extraction_metadata_json["http"]["status"] == 200
        assert revision.extraction_metadata_json["http"]["content_length"] == 9


@pytest.mark.asyncio
@pytest.mark.integration
async def test_acquisition_persists_non_unknown_source_metadata(isolated_paths) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport(
            [HttpResponse(200, {}, b"body", "text/plain", "https://example.test/")]
        ),
    )
    result = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="metadata",
        source_class="PRIMARY",
        publisher="Publisher",
        lineage_id="lineage",
    )
    with Session(engine) as session:
        source = session.get(Source, result.source_id)
        assert (source.source_class, source.publisher, source.lineage_id) == (
            "PRIMARY",
            "Publisher",
            "lineage",
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_retryable_failure_can_use_a_new_attempt_identity(isolated_paths) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    transport = Transport(
        [HttpResponse(200, {}, b"ok", "text/plain", "https://example.test/")]
    )
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        transport,
    )
    service._record_failure(
        "same:attempt:1", "https://example.test/", "policy", "TRANSIENT"
    )
    result = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="same",
        attempt_id="2",
    )
    assert result.extract == "ok"
    with Session(engine) as session:
        assert len(session.scalars(select(ToolEvent)).all()) == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_direct_pdf_uses_pdf_extractor_without_decoding_bytes(
    isolated_paths,
) -> None:
    class Pdf:
        def extract(self, body: bytes) -> str:
            assert body == b"%PDF-\xff\xfe"
            return "extracted PDF"

        def status(self):
            return {"available": True}

        async def close(self):
            pass

    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport(
            [
                HttpResponse(
                    200,
                    {},
                    b"%PDF-\xff\xfe",
                    "application/pdf",
                    "https://example.test/file.pdf",
                )
            ]
        ),
        pdf=Pdf(),
    )
    result = await service.acquire(
        "https://example.test/file.pdf",
        AcquisitionPolicy(),
        idempotency_key="pdf",
    )
    assert result.extract == "extracted PDF"
    replayed = await service.acquire(
        "https://example.test/file.pdf",
        AcquisitionPolicy(),
        idempotency_key="pdf-replay",
    )
    assert replayed.cached is True
    assert replayed.extract == "extracted PDF"


def test_search_snippet_is_lead_only() -> None:
    lead = LeadOnlyResult.from_search("https://example.test", "snippet")
    assert lead.support_role == "LEAD_ONLY"
    assert lead.can_be_evidence is False


@pytest.mark.asyncio
async def test_direct_failure_uses_injected_browser_html(tmp_path: Path) -> None:
    class Browser:
        async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
            return BrowserResult(b"rendered", url, "text/html")

    service = AcquisitionService(
        None,
        BlobStore(tmp_path / "blobs"),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport([]),
        browser=Browser(),
    )
    body, extract = await service.acquire_with_fallback(
        "https://example.test/a", AcquisitionPolicy()
    )
    assert body == b"rendered"
    assert extract == "rendered"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_failed_acquisition_records_compact_idempotent_error_event(
    isolated_paths,
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"bad.test": ("127.0.0.1",)}),
        Transport([]),
    )
    for _attempt in range(2):
        with pytest.raises(UrlPolicyError):
            await service.acquire(
                "https://bad.test/secret",
                AcquisitionPolicy(),
                idempotency_key="failed-once",
            )
    with Session(engine) as session:
        events = session.scalars(
            select(ToolEvent).where(ToolEvent.idempotency_key == "failed-once")
        ).all()
        assert len(events) == 1
        assert events[0].status == "FAILED"
        assert events[0].error_class == "URL_POLICY"
        assert events[0].blob_hash is None
        assert "secret" not in str(events[0].extract_json)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unavailable_browser_is_a_durable_failure_class(isolated_paths) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport([]),
    )
    with pytest.raises(IndexError):
        await service.acquire(
            "https://example.test/rendered",
            AcquisitionPolicy(),
            idempotency_key="browser-unavailable",
        )
    with Session(engine) as session:
        event = session.scalar(
            select(ToolEvent).where(ToolEvent.idempotency_key == "browser-unavailable")
        )
        assert event.error_class == "BROWSER_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_persistent_acquisition_uses_injected_browser(isolated_paths) -> None:
    class Browser:
        async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
            return BrowserResult(b"rendered fallback", url, "text/html")

    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport([]),
        browser=Browser(),
    )
    result = await service.acquire(
        "https://example.test/fallback",
        AcquisitionPolicy(),
        idempotency_key="fallback",
    )
    assert result.extract == "rendered fallback"
    assert service.blobs.get(result.blob_hash) == b"rendered fallback"
