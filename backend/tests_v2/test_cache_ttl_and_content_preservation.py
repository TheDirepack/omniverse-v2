# Focused TDD proof for long content caching and full-document MiniCPM reformat.
# No external network: client fakes only, never run.sh. ruff: noqa: ARG002

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from app.v2.acquisition import AcquisitionPolicy, AcquisitionService, HttpResponse
from app.v2.blobs import BlobStore
from app.v2.config import V2Config
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.preprocessing import (
    MiniCPMPreprocessor,
    ModelPreprocessResult,
    PreprocessingStatus,
    preprocess_document,
)
from app.v2.search import CachedFallbackSearch
from app.v2.wiki import WikiResearchFoundation

WEEK = 7 * 24 * 3600


class Resolver:
    def __init__(self, values: dict[str, tuple[str, ...]]) -> None:
        self.values = values

    async def resolve(self, host: str) -> tuple[str, ...]:
        return self.values[host]


class Transport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses

    async def get(
        self, url: str, *, timeout_seconds: float, max_bytes: int
    ) -> HttpResponse:
        return self.responses.pop(0)


# --------------------------------------------------------------------------- #
# Requirement 1: MiniCPM reformat and preprocessing must NOT drop late content.
# --------------------------------------------------------------------------- #

def test_cleaned_text_keeps_entry_beyond_the_selected_view() -> None:
    lines = [f"Entry {i:02d}: ordinary source detail {i}." for i in range(1, 21)]
    lines[-1] = "Xenolithic mausoleum hoard cypher 9144 Beta."
    source = "\n\n".join(lines)

    doc = preprocess_document(source, "text/plain")
    cleaned = doc.cleaned_text
    selected_text = "\n\n".join(p.text for p in doc.selected_passages)

    assert "Xenolithic mausoleum hoard cypher 9144" in cleaned
    assert "Xenolithic mausoleum hoard cypher 9144" not in selected_text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reformat_input_is_full_document_not_selected_passages(
    isolated_paths,
) -> None:
    """Acquisition must feed MiniCPM the whole cleaned document rather than the
    12 selected passages a low-value/title-only view would collapse to."""

    paragraphs = "".join(
        f"<p>Entry {i:02d}: ordinary source detail {i}.</p>" for i in range(1, 21)
    )
    raw = (
        f"<html><body>{paragraphs}<p>"
        f"Reserve spine nexus 9144 terminal.</p></body></html>"
    ).encode()
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)

    calls: list[str] = []

    class RecordingPreprocessor:
        async def reformat(self, text: str) -> ModelPreprocessResult:
            calls.append(text)
            return ModelPreprocessResult(
                text, PreprocessingStatus.APPLIED, "fake", False
            )

    service = AcquisitionService(
        engine,
        BlobStore(isolated_paths["blobs"]),
        Resolver({"example.test": ("93.184.216.34",)}),
        Transport(
            [
                HttpResponse(
                    200, {}, raw, "text/html", "https://example.test/"
                )
            ]
        ),
        preprocessor=RecordingPreprocessor(),
    )

    result = await service.acquire(
        "https://example.test/",
        AcquisitionPolicy(),
        idempotency_key="full-doc-reformat",
    )

    assert calls, "preprocessor.reformat was never invoked"
    assert "Reserve spine nexus 9144 terminal" in calls[0], (
        "reformat must observe the entire document, not a truncated view"
    )
    assert "Reserve spine nexus 9144 terminal" not in result.extract
    engine.dispose()


@pytest.mark.asyncio
async def test_minicpm_reformat_preserves_entries_when_given_full_text() -> None:
    original = (
        "Overview record.\n"
        "Entry A: gauss lance arrays 512.\n"
        "Entry C archive vault cipher 2206."
    )

    async def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": original}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    adapter = MiniCPMPreprocessor(client=client)
    result = await adapter.reformat(original)
    await client.aclose()

    assert result.status is PreprocessingStatus.APPLIED
    assert "Entry C archive vault cipher 2206" in result.text


# --------------------------------------------------------------------------- #
# Requirement: chunked reformat splits only at structural boundaries so a chunk
# never slices through the middle of a paragraph/table and leaves garbled text.
# --------------------------------------------------------------------------- #

def test_reformat_chunks_only_at_block_boundaries_and_reconstructs() -> None:
    adapter = MiniCPMPreprocessor(model="mini", context_tokens=4000)
    text = "\n\n".join(
        f"Paragraph {index} walks over the moor each night." for index in range(160)
    )
    chunks = adapter._chunk_for_context(text)
    assert len(chunks) > 1, "expected the document to split into multiple chunks"
    assert "\n\n".join(chunks) == text, "chunks must reconstruct the full text"
    blocks = text.split("\n\n")
    for chunk in chunks:
        for part in chunk.split("\n\n"):
            assert part in blocks, f"chunk bisects a block: {part[:40]!r}"


@pytest.mark.asyncio
async def test_chunked_reformat_joins_validated_chunks_in_order() -> None:
    blocks = [f"Entry number {index} stays intact." for index in range(60)]
    original = "\n\n".join(blocks)

    requested: list[str] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requested.append(request.headers.get("content-length", "0"))
        payload = json.loads(request.content)
        content = payload["messages"][1]["content"]
        inner = content.removeprefix("<untrusted_page>\n").removesuffix(
            "\n</untrusted_page>"
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": inner}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    adapter = MiniCPMPreprocessor(client=client, context_tokens=500)
    result = await adapter.reformat(original)
    await client.aclose()

    assert result.status is PreprocessingStatus.APPLIED
    assert result.used_fallback is False
    assert result.text == original
    assert len(requested) > 1, "expected multiple chunked reformat requests"


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_chunks", [(1,), (0, 1, 2)])
async def test_chunked_reformat_preserves_all_text_after_chunk_failure(
    monkeypatch: pytest.MonkeyPatch, failed_chunks: tuple[int, ...]
) -> None:
    chunks = [f"Entry number {index} stays intact." for index in range(3)]
    requested = []

    async def respond(request: httpx.Request) -> httpx.Response:
        index = len(requested)
        requested.append(json.loads(request.content))
        if index in failed_chunks:
            return httpx.Response(503, json={"error": "temporary failure"})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": chunks[index]}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        adapter = MiniCPMPreprocessor(client=client)
        monkeypatch.setattr(adapter, "_chunk_for_context", lambda _text: chunks)
        result = await adapter.reformat("\n\n".join(chunks))

    assert len(requested) == 3
    assert result.text == "\n\n".join(chunks)
    assert result.status is PreprocessingStatus.APPLIED
    assert result.used_fallback is True
    assert "chunk 2/3" in result.detail


@pytest.mark.asyncio
async def test_reformat_single_chunk_behaves_like_a_plain_request() -> None:
    original = "One short paragraph that fits in a single chunk."

    async def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": original}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    adapter = MiniCPMPreprocessor(client=client)
    result = await adapter.reformat(original)
    await client.aclose()

    assert result.status is PreprocessingStatus.APPLIED
    assert result.used_fallback is False


# --------------------------------------------------------------------------- #
# Requirement 2: long (one-week default) content cache freshness, overridable.
# --------------------------------------------------------------------------- #

def test_cache_ttl_defaults_to_a_week_and_is_env_overridable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    defaults = V2Config.from_env()
    assert defaults.cache_ttl_seconds == WEEK

    monkeypatch.setenv("OMNIVERSE_V2_CACHE_TTL_SECONDS", "3600")
    configured = V2Config.from_env()
    assert configured.cache_ttl_seconds == 3600


class StubSearchProvider:
    async def search(self, query: str, *, limit: int):
        return ()


def test_acquisition_search_and_wiki_read_the_config_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Default (no override) is a week everywhere.
    assert AcquisitionPolicy().freshness_seconds == WEEK
    assert CachedFallbackSearch((StubSearchProvider(),)).ttl_seconds == WEEK

    # The cache knob is overridable through the same env variable.
    monkeypatch.setenv("OMNIVERSE_V2_CACHE_TTL_SECONDS", "120")
    assert AcquisitionPolicy().freshness_seconds == 120
    assert CachedFallbackSearch((StubSearchProvider(),)).ttl_seconds == 120

    # Wiki inventory freshness is driven by the acquisition policy value.
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    profile = SimpleNamespace(inventory_fetched_at=now)
    freshness = AcquisitionPolicy().freshness_seconds
    assert WikiResearchFoundation._is_fresh(
        profile, now + timedelta(seconds=30), freshness
    )
    assert not WikiResearchFoundation._is_fresh(
        profile, now + timedelta(seconds=300), freshness
    )
