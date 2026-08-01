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
from app.v2.preprocessing import ModelPreprocessResult, PreprocessingStatus


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
    raw = b"<html><body>rendered<script>ignored</script></body></html>"

    class Browser:
        async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
            return BrowserResult(raw, url, "text/html")

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
    assert body == raw
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
    raw = (
        b"<html><body><main>rendered <div>fallback</div>"
        b"<nav>ignored</nav></main></body></html>"
    )

    class Browser:
        async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
            return BrowserResult(raw, url, "text/html")

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
    assert result.extract == "rendered\n\nfallback"
    assert service.blobs.get(result.blob_hash) == raw


class RecordingPreprocessor:
    def __init__(
        self,
        *,
        output: str | None = None,
        status: PreprocessingStatus = PreprocessingStatus.APPLIED,
        events: list[str] | None = None,
    ) -> None:
        self.output = output
        self.status = status
        self.events = events
        self.calls: list[str] = []

    async def reformat(self, text: str) -> ModelPreprocessResult:
        self.calls.append(text)
        if self.events is not None:
            self.events.append("minicpm")
        fallback = self.status is not PreprocessingStatus.APPLIED
        return ModelPreprocessResult(
            text if fallback or self.output is None else self.output,
            self.status,
            "fake preprocessor",
            fallback,
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_targeting_selects_only_matching_historical_section(
    isolated_paths,
) -> None:
    raw = (
        b"<html><body><h1>Overview</h1><p>Current fleet details.</p>"
        b"<h2>Historical record</h2><p>The old gate opened in 1897.</p>"
        b"<h2>Modern era</h2><p>The replacement opened in 2020.</p></body></html>"
    )
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    preprocessor = RecordingPreprocessor(output="Historical record: old gate, 1897.")
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport([HttpResponse(200, {}, raw, "text/html", "https://example.test/")]),
        preprocessor=preprocessor,
    )

    result = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="historical-target",
        exact_phrases=("old gate opened",),
        section_hints=("Historical record",),
    )

    assert result.targeting_status == "MATCHED"
    assert [item["text"] for item in result.authoritative_passages] == [
        "Historical record",
        "The old gate opened in 1897.",
    ]
    assert "Modern era" not in result.extract
    assert preprocessor.calls == [result.extract]
    with Session(engine) as session:
        revision = session.get(SourceRevision, result.revision_id)
        metadata = revision.extraction_metadata_json
    assert metadata["deterministic"]["selected_locators"] == [
        item["locator"] for item in result.authoritative_passages
    ]
    assert metadata["minicpm"]["status"] == "APPLIED"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_targeting_no_match_never_broadens_or_calls_minicpm(
    isolated_paths,
) -> None:
    raw = b"<html><body><h1>Modern era</h1><p>Only current facts.</p></body></html>"
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    preprocessor = RecordingPreprocessor(output="should not run")
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport([HttpResponse(200, {}, raw, "text/html", "https://example.test/")]),
        preprocessor=preprocessor,
    )

    result = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="missing-target",
        exact_phrases=("ancient collapse",),
    )

    assert result.targeting_status == "NO_RELEVANT_PASSAGE"
    assert result.authoritative_passages == ()
    assert result.extract == ""
    assert result.readability_text == ""
    assert result.preprocessing_status == "NOT_RUN"
    assert preprocessor.calls == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_xhtml_preserves_unknown_wrapper_text_before_minicpm(
    isolated_paths,
) -> None:
    raw = (
        b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">'
        b"<body><custom-wiki-tag>Preserved wiki fact.</custom-wiki-tag></body></html>"
    )
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    preprocessor = RecordingPreprocessor()
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport(
            [
                HttpResponse(
                    200,
                    {},
                    raw,
                    "application/xhtml+xml",
                    "https://example.test/wiki",
                )
            ]
        ),
        preprocessor=preprocessor,
    )

    result = await service.acquire(
        "https://example.test/wiki", AcquisitionPolicy(), idempotency_key="xhtml"
    )

    assert result.extract == "Preserved wiki fact."
    assert preprocessor.calls == ["Preserved wiki fact."]
    assert service.blobs.get(result.blob_hash) == raw


@pytest.mark.asyncio
@pytest.mark.integration
async def test_targeted_derivatives_are_not_reused_for_different_hints(
    isolated_paths,
) -> None:
    raw = b"<h1>History</h1><p>Old gate opened.</p><h1>Fleet</h1><p>Nova has ships.</p>"
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    transport = Transport(
        [
            HttpResponse(200, {}, raw, "text/html", "https://example.test/"),
            HttpResponse(200, {}, raw, "text/html", "https://example.test/"),
        ]
    )
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        transport,
    )

    history = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="history",
        section_hints=("History",),
    )
    fleet = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="fleet",
        section_hints=("Fleet",),
    )
    replayed_fleet = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="fleet",
        section_hints=("Fleet",),
    )

    assert "Old gate" in history.extract
    assert "Nova has ships" not in history.extract
    assert "Nova has ships" in fleet.extract
    assert "Old gate" not in fleet.extract
    assert replayed_fleet.extract == fleet.extract
    assert replayed_fleet.deterministic_blob_hash == fleet.deterministic_blob_hash
    assert transport.calls == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_minicpm_failure_falls_back_and_cached_result_reuses_derivatives(
    isolated_paths,
) -> None:
    raw = b"<html><body><h1>Facts</h1><p>Captain Nova has 20 ships.</p></body></html>"
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    preprocessor = RecordingPreprocessor(status=PreprocessingStatus.UNGROUNDED_OUTPUT)
    transport = Transport(
        [HttpResponse(200, {}, raw, "text/html", "https://example.test/")]
    )
    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        transport,
        preprocessor=preprocessor,
    )

    first = await service.acquire(
        "https://example.test/", AcquisitionPolicy(), idempotency_key="first"
    )
    cached = await service.acquire(
        "https://example.test/", AcquisitionPolicy(), idempotency_key="cached"
    )

    assert first.preprocessing_status == "UNGROUNDED_OUTPUT"
    assert first.readability_text == first.extract
    assert first.deterministic_blob_hash
    assert first.readability_blob_hash
    assert cached.cached is True
    assert cached.authoritative_passages == first.authoritative_passages
    assert cached.deterministic_blob_hash == first.deterministic_blob_hash
    assert cached.readability_blob_hash == first.readability_blob_hash
    assert cached.preprocessing_status == first.preprocessing_status
    assert transport.calls == 1
    assert len(preprocessor.calls) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_production_acquisition_orders_raw_deterministic_and_minicpm(
    isolated_paths, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.v2.acquisition as acquisition_module

    events: list[str] = []
    raw = b"<html><body><p>Target fact.</p></body></html>"

    class OrderedTransport(Transport):
        async def get(self, url: str, *, timeout_seconds: float, max_bytes: int):
            events.append("fetch")
            return await super().get(
                url, timeout_seconds=timeout_seconds, max_bytes=max_bytes
            )

    class OrderedBlobs(BlobStore):
        def put(self, body: bytes) -> str:
            events.append("blob:raw" if body == raw else "blob:derivative")
            return super().put(body)

    original = acquisition_module.preprocess_document

    def ordered_preprocess(*args, **kwargs):
        events.append("deterministic")
        return original(*args, **kwargs)

    monkeypatch.setattr(acquisition_module, "preprocess_document", ordered_preprocess)
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    service = AcquisitionService(
        engine,
        OrderedBlobs(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        OrderedTransport(
            [HttpResponse(200, {}, raw, "text/html", "https://example.test/")]
        ),
        preprocessor=RecordingPreprocessor(events=events),
    )

    await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="ordered",
        exact_phrases=("Target fact",),
    )

    assert events[0:3] == ["fetch", "blob:raw", "deterministic"]
    assert events.index("deterministic") < events.index("minicpm")
    assert events.index("minicpm") < len(events) - 1
