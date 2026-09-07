# Deterministic fakes exercise the wiki boundary without external network access.

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.v2 import wiki
from app.v2.acquisition import (
    AcquisitionPolicy,
    AcquisitionResult,
    AcquisitionService,
    HttpResponse,
)
from app.v2.blobs import BlobStore
from app.v2.contracts import CreateResearchRun, ResearchRunTargetInput
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.domain import StepKind
from app.v2.models import (
    CanonNode,
    ResearchWorkspace,
    WikiInventoryPage,
    WikiPageQueue,
    WikiProfile,
    WorkspaceKnowledgePublication,
    World,
)
from app.v2.providers import ModelResponse, Usage
from app.v2.research_runs import ResearchRunKernel
from app.v2.search import SearchCandidate
from app.v2.wiki import WikiResearchFoundation, parse_sitemap_xml
from app.v2.workflow import ResearchWorkflow

SCOPE = {
    "continuity": "prime",
    "era_or_timepoint": "unspecified",
    "branch_id": "main",
    "conditions": [],
}


class Resolver:
    async def resolve(self, host: str) -> tuple[str, ...]:
        assert host == "wiki.test"
        return ("93.184.216.34",)


class SitemapTransport:
    def __init__(self, body: bytes, content_type: str = "application/xml") -> None:
        self.body = body
        self.content_type = content_type
        self.calls: list[str] = []

    async def get(
        self, url: str, *, timeout_seconds: float, max_bytes: int
    ) -> HttpResponse:
        self.calls.append(url)
        return HttpResponse(200, {}, self.body, self.content_type, url)


@pytest.fixture
def wiki_parts(isolated_paths: dict[str, Path]) -> tuple[Engine, BlobStore]:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        session.add(
            World(
                id="world-1",
                name="Example World",
                franchise="Example",
                category="SF",
                continuity="prime",
            )
        )
    return engine, BlobStore(isolated_paths["blobs"])


@pytest.mark.asyncio
async def test_sitemap_cache_parsing_and_same_wiki_restriction(
    wiki_parts: tuple[Engine, BlobStore],
) -> None:
    engine, blobs = wiki_parts
    body = b"""<?xml version='1.0'?>
    <urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
      <url><loc>https://wiki.test/wiki/Alpha</loc></url>
      <url><loc>HTTPS://WIKI.TEST:443/wiki/Alpha#duplicate</loc></url>
      <url><loc>https://evil.test/wiki/Steal</loc></url>
    </urlset>"""
    parsed = parse_sitemap_xml(body, "https://wiki.test/sitemap.xml")
    assert parsed.page_urls == ("https://wiki.test/wiki/Alpha",)

    transport = SitemapTransport(body)
    acquisition = AcquisitionService(engine, blobs, Resolver(), transport)
    foundation = WikiResearchFoundation(
        engine, acquisition, clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    profile = await foundation.qualify_candidate(
        world_id="world-1",
        scope=SCOPE,
        candidate=SearchCandidate(
            canonical_url="https://wiki.test/wiki/Example_World",
            title="Example World Wiki",
            snippet="",
            rank=1,
        ),
        policy=AcquisitionPolicy(),
    )

    assert profile is not None
    assert transport.calls == ["https://wiki.test/sitemap.xml"]
    cached = await foundation.refresh_inventory(profile.id, AcquisitionPolicy())
    assert cached.cache_hit is True
    assert transport.calls == ["https://wiki.test/sitemap.xml"]
    with Session(engine) as session:
        assert session.scalars(select(WikiInventoryPage.canonical_url)).all() == [
            "https://wiki.test/wiki/Alpha"
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("content_type", ["application/gzip", "application/x-gzip"])
async def test_qualify_sitemap_index_with_compressed_child(
    wiki_parts: tuple[Engine, BlobStore], content_type: str
) -> None:
    engine, blobs = wiki_parts
    child_url = "https://wiki.test/sitemap/pages.xml.gz"
    body = b"""<urlset>
      <url><loc>https://wiki.test/wiki/Alpha</loc><lastmod>2026-01-01</lastmod></url>
      <url><loc>https://evil.test/wiki/Steal</loc></url>
    </urlset>"""
    policy = AcquisitionPolicy()

    class IndexTransport(SitemapTransport):
        async def get(self, url, *, timeout_seconds, max_bytes):
            assert max_bytes == policy.max_body_bytes == 5_000_000
            assert timeout_seconds == policy.timeout_seconds
            if url.endswith("/sitemap.xml"):
                self.calls.append(url)
                return HttpResponse(
                    200,
                    {},
                    f"<sitemapindex><sitemap><loc>{child_url}</loc>"
                    "</sitemap></sitemapindex>".encode(),
                    "application/xml",
                    url,
                )
            assert url == child_url
            return await super().get(
                url, timeout_seconds=timeout_seconds, max_bytes=max_bytes
            )

    transport = IndexTransport(gzip.compress(body), content_type)
    acquisition = AcquisitionService(engine, blobs, Resolver(), transport)
    foundation = WikiResearchFoundation(engine, acquisition)
    profile = await foundation.qualify_candidate(
        world_id="world-1",
        scope=SCOPE,
        candidate=SearchCandidate(
            canonical_url="https://wiki.test/wiki/Example_World",
            title="Example World Wiki",
            snippet="",
            rank=1,
        ),
        policy=policy,
    )
    assert profile is not None
    assert transport.calls == ["https://wiki.test/sitemap.xml", child_url]
    with Session(engine) as session:
        pages = session.scalars(select(WikiInventoryPage)).all()
        assert [(page.canonical_url, page.last_modified) for page in pages] == [
            ("https://wiki.test/wiki/Alpha", "2026-01-01")
        ]
    assert policy == AcquisitionPolicy()
    with pytest.raises(ValueError, match="content type is not allowed"):
        await acquisition.fetch_http(child_url, policy)


@pytest.mark.asyncio
@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("over_limit", [False, True])
async def test_sitemap_xml_size_cap(
    wiki_parts: tuple[Engine, BlobStore],
    monkeypatch,
    compressed: bool,
    over_limit: bool,
) -> None:
    engine, blobs = wiki_parts
    body = (
        b"<urlset><url><loc>https://wiki.test/wiki/Alpha</loc></url>"
        + b" " * 4096
        + b"</urlset>"
    )
    monkeypatch.setattr(wiki, "_MAX_SITEMAP_XML_BYTES", len(body) - over_limit)
    transport = SitemapTransport(gzip.compress(body) if compressed else body)
    foundation = WikiResearchFoundation(
        engine, AcquisitionService(engine, blobs, Resolver(), transport)
    )
    document = await foundation._fetch_sitemap(
        "https://wiki.test/sitemap.xml", AcquisitionPolicy()
    )
    assert document.page_urls == (
        () if over_limit else ("https://wiki.test/wiki/Alpha",)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["invalid", "truncated", "crc", "deflate", "dtd"])
async def test_unsafe_compressed_sitemap_fails_closed(
    wiki_parts: tuple[Engine, BlobStore], kind: str
) -> None:
    engine, blobs = wiki_parts
    xml = b"<urlset><url><loc>https://wiki.test/wiki/Alpha</loc></url></urlset>"
    compressed = gzip.compress(xml)
    bodies = {
        "invalid": b"\x1f\x8bnot gzip",
        "truncated": compressed[:-1],
        "crc": compressed[:-8] + b"\x00" * 8,
        "deflate": compressed[:10] + b"\x07" + compressed[11:],
        "dtd": gzip.compress(b"<!DOCTYPE urlset>" + xml),
    }
    foundation = WikiResearchFoundation(
        engine,
        AcquisitionService(
            engine,
            blobs,
            Resolver(),
            SitemapTransport(bodies[kind], "application/gzip"),
        ),
    )
    document = await foundation._fetch_sitemap(
        "https://wiki.test/sitemap.xml", AcquisitionPolicy()
    )
    assert document.page_entries == document.sitemap_urls == ()


@pytest.mark.asyncio
async def test_sitemap_already_decoded_by_transport(
    wiki_parts: tuple[Engine, BlobStore],
) -> None:
    engine, blobs = wiki_parts

    class DecodedTransport:
        async def get(self, url, *, timeout_seconds, max_bytes):
            return HttpResponse(
                200,
                {"content-encoding": "gzip"},
                b"<urlset><url><loc>https://wiki.test/wiki/Alpha</loc></url></urlset>",
                "application/x-gzip",
                url,
            )

    foundation = WikiResearchFoundation(
        engine, AcquisitionService(engine, blobs, Resolver(), DecodedTransport())
    )
    document = await foundation._fetch_sitemap(
        "https://wiki.test/sitemap.xml.gz", AcquisitionPolicy()
    )
    assert document.page_urls == ("https://wiki.test/wiki/Alpha",)


@pytest.mark.asyncio
@pytest.mark.parametrize("rejection", ["download_limit", "octet_stream"])
async def test_sitemap_retains_acquisition_restrictions(
    wiki_parts: tuple[Engine, BlobStore], rejection: str
) -> None:
    engine, blobs = wiki_parts
    body = gzip.compress(b"<urlset/>")
    policy = AcquisitionPolicy(max_body_bytes=len(body) - 1)
    content_type = "application/gzip"
    message = "response body exceeds policy"
    if rejection == "octet_stream":
        policy = AcquisitionPolicy()
        content_type = "application/octet-stream"
        message = "content type is not allowed"
    foundation = WikiResearchFoundation(
        engine,
        AcquisitionService(
            engine, blobs, Resolver(), SitemapTransport(body, content_type)
        ),
    )
    with pytest.raises(ValueError, match=message):
        await foundation._fetch_sitemap("https://wiki.test/sitemap.xml.gz", policy)


class RecordingSearch:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def search(self, query: str, *, limit: int):
        self.calls.append(query)
        raise AssertionError


class Router:
    def __init__(self, *, title_only: bool = False) -> None:
        self.title_only = title_only
        self.requests = []

    async def complete(self, task, request, requirements):
        self.requests.append((task, request))
        if task == "research.plan":
            result = {
                "questions": [
                    {
                        "id": "q1",
                        "priority": 1,
                        "question": "What does the fusion engine do?",
                        "queries": ["fusion engine capability"],
                        "source_budget": 1,
                        "stop_conditions": ["one source"],
                    }
                ]
            }
        elif task == "research.extract":
            excerpt = (
                "Fusion Engine"
                if self.title_only
                else "The fusion engine bends local spacetime."
            )
            result = {
                "fragments": [
                    {
                        "fragment_id": "fragment-fusion",
                        "source_revision_id": "revision-fusion",
                        "locator": "section:0/passage:0",
                        "exact_excerpt": excerpt,
                        "normalized_statement": excerpt,
                        "subject_ids": ["fusion-engine"],
                        "continuity": "prime",
                        "temporal_scope": {
                            "valid_from": None,
                            "valid_to": None,
                            "branch_id": "main",
                        },
                        "support_role": "SUPPORTS",
                        "extraction_confidence": 0.9,
                    }
                ]
            }
        else:
            raise AssertionError(task)
        return ModelResponse(
            text=json.dumps(result),
            tool_calls=(),
            usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2),
        )


class PageAcquisition:
    def __init__(
        self, engine: Engine, blobs: BlobStore, *, title_only: bool = False
    ) -> None:
        self.engine = engine
        self.blobs = blobs
        self.title_only = title_only

    async def acquire(self, url, policy, *, source_class="SECONDARY", **kwargs):
        text = (
            "Fusion Engine"
            if self.title_only
            else "The fusion engine bends local spacetime."
        )
        blob_hash = self.blobs.put(text.encode())
        from app.v2.models import Source, SourceRevision

        with Session(self.engine) as session, session.begin():
            if session.get(Source, "source-fusion") is None:
                session.add(
                    Source(
                        id="source-fusion",
                        canonical_url=url,
                        source_class=source_class,
                    )
                )
            if session.get(SourceRevision, "revision-fusion") is None:
                session.add(
                    SourceRevision(
                        id="revision-fusion",
                        source_id="source-fusion",
                        content_hash=blob_hash,
                        blob_hash=blob_hash,
                        content_type="text/plain",
                    )
                )
        return AcquisitionResult(
            "source-fusion",
            "revision-fusion",
            url,
            blob_hash,
            text,
            False,
            "text/plain",
            authoritative_passages=(
                {"locator": "section:0/passage:0", "text": text},
            ),
            readability_text=text,
        )


def add_fresh_wiki(engine: Engine, *, title: str = "Fusion Engine") -> None:
    now = datetime.now(timezone.utc)
    with Session(engine) as session, session.begin():
        profile = WikiProfile(
            id="wiki-profile",
            world_id="world-1",
            continuity="prime",
            era_or_timepoint="unspecified",
            branch_id="main",
            conditions_key="[]",
            canonical_url="https://wiki.test/",
            sitemap_url="https://wiki.test/sitemap.xml",
            source_class="SECONDARY",
            qualified_at=now,
            inventory_fetched_at=now,
        )
        session.add(profile)
        session.flush()
        session.add(
            WikiInventoryPage(
                id="wiki-page-fusion",
                profile_id=profile.id,
                canonical_url="https://wiki.test/wiki/Fusion_Engine",
                title=title,
                aliases_json=["fusion engine"],
                section_terms_json=["capability", "spacetime"],
                active=True,
            )
        )


def create_run(engine: Engine, key: str):
    return ResearchRunKernel(engine).create(
        CreateResearchRun(
            objective="Document fusion engine",
            scope=SCOPE,
            targets=(ResearchRunTargetInput(world_id="world-1"),),
        ),
        key,
    )


@pytest.mark.asyncio
async def test_qualified_inventory_suppresses_search_and_publishes_context(
    wiki_parts: tuple[Engine, BlobStore],
) -> None:
    engine, blobs = wiki_parts
    add_fresh_wiki(engine)
    search = RecordingSearch()
    first_router = Router()
    run = create_run(engine, "wiki-first-one")
    workflow = ResearchWorkflow(
        engine,
        ResearchRunKernel(engine),
        first_router,
        search,
        PageAcquisition(engine, blobs),
    )

    await workflow.run(run.id, stop_after=StepKind.EXTRACT)

    assert search.calls == []
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(CanonNode)) == 0
        assert session.scalar(
            select(func.count()).select_from(WorkspaceKnowledgePublication)
        ) == 1
    later_router = Router()
    later = create_run(engine, "wiki-first-later")
    await ResearchWorkflow(
        engine,
        ResearchRunKernel(engine),
        later_router,
        search,
        PageAcquisition(engine, blobs),
    ).run(later.id, stop_after=StepKind.PLAN)
    planner_payload = json.loads(later_router.requests[0][1].messages[-1]["content"])[
        "task"
    ]
    assert planner_payload["cumulative_research_context"] == [
        {
            "fragment_id": "fragment-fusion",
            "source_revision_id": "revision-fusion",
            "exact_excerpt": "The fusion engine bends local spacetime.",
        }
    ]


@pytest.mark.asyncio
async def test_title_only_page_does_not_publish_reusable_knowledge(
    wiki_parts: tuple[Engine, BlobStore],
) -> None:
    engine, blobs = wiki_parts
    add_fresh_wiki(engine, title="Fusion Engine")
    run = create_run(engine, "wiki-title-only")

    await ResearchWorkflow(
        engine,
        ResearchRunKernel(engine),
        Router(title_only=True),
        RecordingSearch(),
        PageAcquisition(engine, blobs, title_only=True),
    ).run(run.id, stop_after=StepKind.EXTRACT)

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(WorkspaceKnowledgePublication)
        ) == 0


def test_queue_dedupes_alias_section_matches_and_defers_external_work(
    wiki_parts: tuple[Engine, BlobStore],
) -> None:
    engine, _blobs = wiki_parts
    add_fresh_wiki(engine, title="Chronicle")
    run = create_run(engine, "wiki-queue")
    workspace_id = f"workspace:{run.targets[0].id}"
    workspace = ResearchWorkspace(
        id=workspace_id,
        run_id=run.id,
        target_id=run.targets[0].id,
        world_id="world-1",
        continuity="prime",
        brief_json={},
        status="ACTIVE",
    )
    with Session(engine) as session, session.begin():
        page = session.get(WikiInventoryPage, "wiki-page-fusion")
        assert page is not None
        page.aliases_json = ["Old Gate"]
        page.section_terms_json = ["history"]
        session.add(workspace)
    foundation = WikiResearchFoundation(engine, None)
    selected = foundation.select_and_enqueue(
        profile_id="wiki-profile",
        workspace_id=workspace_id,
        questions=(
            {
                "id": "q-history",
                "priority": 1,
                "question": "When did the old gate open?",
                "queries": ["old gate history"],
                "source_budget": 1,
            },
            {
                "id": "q-gate",
                "priority": 2,
                "question": "What is the old gate?",
                "queries": ["old gate"],
                "source_budget": 1,
            },
        ),
    )

    assert [item.question_ids for item in selected] == [
        ("q-history", "q-gate"),
    ]
    assert foundation.should_defer_external_work(workspace_id) is True
    with Session(engine) as session, session.begin():
        queue = session.scalar(select(WikiPageQueue))
        assert queue is not None
        queue.status = "ACQUIRED"
    assert foundation.should_defer_external_work(workspace_id) is False
