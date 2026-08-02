"""Durable, service-controlled wiki discovery, inventory, and work selection."""

# Stable boundary diagnostics are intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.v2.acquisition import AcquisitionPolicy, canonicalize_url
from app.v2.models import WikiInventoryPage, WikiPageQueue, WikiProfile

_TERMINAL_QUEUE_STATUSES = frozenset(
    {"ACQUIRED", "NO_RELEVANT_PASSAGE", "ACQUISITION_FAILED"}
)
_MAX_SITEMAP_INDEXES = 8
_MAX_INVENTORY_PAGES = 500
_TERM_PATTERN = re.compile(r"[a-z0-9]{3,}")


@dataclass(frozen=True, slots=True)
class SitemapEntry:
    canonical_url: str
    last_modified: str | None


@dataclass(frozen=True, slots=True)
class SitemapDocument:
    page_entries: tuple[SitemapEntry, ...]
    sitemap_urls: tuple[str, ...]

    @property
    def page_urls(self) -> tuple[str, ...]:
        return tuple(entry.canonical_url for entry in self.page_entries)


@dataclass(frozen=True, slots=True)
class QualifiedWikiProfile:
    id: str
    world_id: str
    continuity: str
    era_or_timepoint: str
    branch_id: str
    conditions_key: str
    canonical_url: str
    sitemap_url: str
    source_class: str
    publisher: str | None
    lineage_id: str | None
    qualified_at: datetime
    inventory_fetched_at: datetime | None


@dataclass(frozen=True, slots=True)
class WikiInventoryRefresh:
    profile: QualifiedWikiProfile
    cache_hit: bool
    page_count: int


@dataclass(frozen=True, slots=True)
class WikiQueueSelection:
    queue_id: str
    inventory_page_id: str
    canonical_url: str
    title: str
    question_ids: tuple[str, ...]
    priority: int
    score: int


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name and child.text:
            value = child.text.strip()
            if value:
                return value
    return None


def parse_sitemap_xml(body: bytes, sitemap_url: str) -> SitemapDocument:
    """Parse a bounded sitemap without resolving entities or accepting other hosts."""

    upper = body.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        return SitemapDocument((), ())
    try:
        canonical_sitemap = canonicalize_url(sitemap_url)
        root = ElementTree.fromstring(body)
    except (DefusedXmlException, ElementTree.ParseError, TypeError, ValueError):
        return SitemapDocument((), ())
    sitemap_host = urlsplit(canonical_sitemap).hostname
    if sitemap_host is None:
        return SitemapDocument((), ())
    root_kind = _local_name(root.tag)
    if root_kind not in {"urlset", "sitemapindex"}:
        return SitemapDocument((), ())
    entries: dict[str, SitemapEntry] = {}
    sitemap_urls: set[str] = set()
    for item in root:
        if _local_name(item.tag) != ("url" if root_kind == "urlset" else "sitemap"):
            continue
        raw_location = _child_text(item, "loc")
        if raw_location is None:
            continue
        try:
            canonical = canonicalize_url(raw_location)
        except (TypeError, ValueError):
            continue
        if urlsplit(canonical).hostname != sitemap_host:
            continue
        if root_kind == "urlset":
            entries.setdefault(
                canonical,
                SitemapEntry(canonical, _child_text(item, "lastmod")),
            )
        else:
            sitemap_urls.add(canonical)
    return SitemapDocument(
        tuple(entries[url] for url in sorted(entries)), tuple(sorted(sitemap_urls))
    )


def _scope_key(scope: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(scope.get("continuity", "unspecified")),
        str(scope.get("era_or_timepoint", "unspecified")),
        str(scope.get("branch_id", "main")),
        json.dumps(sorted(scope.get("conditions", ())), separators=(",", ":")),
    )


def _stable_id(prefix: str, *parts: object) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}-{hashlib.sha256(encoded.encode()).hexdigest()[:24]}"


def _profile_record(profile: WikiProfile) -> QualifiedWikiProfile:
    return QualifiedWikiProfile(
        id=profile.id,
        world_id=profile.world_id,
        continuity=profile.continuity,
        era_or_timepoint=profile.era_or_timepoint,
        branch_id=profile.branch_id,
        conditions_key=profile.conditions_key,
        canonical_url=profile.canonical_url,
        sitemap_url=profile.sitemap_url,
        source_class=profile.source_class,
        publisher=profile.publisher,
        lineage_id=profile.lineage_id,
        qualified_at=profile.qualified_at,
        inventory_fetched_at=profile.inventory_fetched_at,
    )


def _inventory_metadata(canonical_url: str) -> tuple[str, list[str], list[str]]:
    path = unquote(urlsplit(canonical_url).path).rstrip("/")
    leaf = path.rsplit("/", 1)[-1] or "Wiki page"
    title = re.sub(r"[_-]+", " ", leaf).strip() or "Wiki page"
    title = re.sub(r"\s+", " ", title)
    aliases = [title]
    terms = sorted(set(_TERM_PATTERN.findall(title.casefold())))
    return title, aliases, terms


def _terms(value: str) -> set[str]:
    return set(_TERM_PATTERN.findall(value.casefold()))


def _match_score(page: WikiInventoryPage, question: dict[str, Any]) -> int:
    request_text = " ".join(
        [str(question.get("question", "")), *question.get("queries", ())]
    ).casefold()
    request_terms = _terms(request_text)
    if not request_terms:
        return 0
    score = 0
    for text, weight in (
        (page.title, 4),
        *((alias, 3) for alias in page.aliases_json),
        *((term, 2) for term in page.section_terms_json),
    ):
        normalized = " ".join(_TERM_PATTERN.findall(str(text).casefold()))
        if normalized and normalized in request_text:
            score += weight * 10
        score += weight * len(_terms(str(text)) & request_terms)
    return score


class WikiResearchFoundation:
    """Owns URL validation, cached sitemap ingestion, and deterministic page queues."""

    def __init__(self, engine, acquisition, *, clock=None) -> None:
        self.engine = engine
        self.acquisition = acquisition
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def profile_for_scope(
        self, world_id: str, scope: dict[str, Any]
    ) -> QualifiedWikiProfile | None:
        continuity, era_or_timepoint, branch_id, conditions_key = _scope_key(scope)
        with Session(self.engine) as session:
            profile = session.scalar(
                select(WikiProfile).where(
                    WikiProfile.world_id == world_id,
                    WikiProfile.continuity == continuity,
                    WikiProfile.era_or_timepoint == era_or_timepoint,
                    WikiProfile.branch_id == branch_id,
                    WikiProfile.conditions_key == conditions_key,
                )
            )
            return _profile_record(profile) if profile is not None else None

    @staticmethod
    def _is_fresh(profile: WikiProfile, now: datetime, freshness_seconds: int) -> bool:
        if profile.inventory_fetched_at is None:
            return False
        fetched_at = profile.inventory_fetched_at
        if fetched_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return fetched_at + timedelta(seconds=freshness_seconds) > now

    async def qualify_candidate(
        self,
        *,
        world_id: str,
        scope: dict[str, Any],
        candidate,
        policy: AcquisitionPolicy,
    ) -> QualifiedWikiProfile | None:
        """Persist a profile only after its same-host sitemap yields usable pages."""

        if self.acquisition is None:
            raise RuntimeError("wiki qualification requires an acquisition service")
        try:
            discovered_url = canonicalize_url(str(candidate.canonical_url))
            parsed = urlsplit(discovered_url)
            root = urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))
            canonical_root = await self.acquisition.validate_url(root, policy)
            sitemap_url = canonicalize_url(f"{canonical_root.rstrip('/')}/sitemap.xml")
            await self.acquisition.validate_url(sitemap_url, policy)
        except (TypeError, ValueError):
            return None
        continuity, era_or_timepoint, branch_id, conditions_key = _scope_key(scope)
        created = False
        with Session(self.engine) as session, session.begin():
            profile = session.scalar(
                select(WikiProfile).where(
                    WikiProfile.world_id == world_id,
                    WikiProfile.continuity == continuity,
                    WikiProfile.era_or_timepoint == era_or_timepoint,
                    WikiProfile.branch_id == branch_id,
                    WikiProfile.conditions_key == conditions_key,
                )
            )
            if profile is None:
                profile = WikiProfile(
                    id=_stable_id(
                        "wiki-profile",
                        world_id,
                        continuity,
                        era_or_timepoint,
                        branch_id,
                        conditions_key,
                    ),
                    world_id=world_id,
                    continuity=continuity,
                    era_or_timepoint=era_or_timepoint,
                    branch_id=branch_id,
                    conditions_key=conditions_key,
                    canonical_url=canonical_root,
                    sitemap_url=sitemap_url,
                    source_class=str(
                        getattr(candidate, "source_class", "SECONDARY") or "SECONDARY"
                    ).upper(),
                    publisher=getattr(candidate, "publisher", None),
                    lineage_id=getattr(candidate, "lineage_id", None),
                    qualified_at=self.clock(),
                    inventory_fetched_at=None,
                )
                session.add(profile)
                created = True
            profile_id = profile.id
        try:
            refreshed = await self.refresh_inventory(profile_id, policy)
        except (ConnectionError, OSError, TimeoutError, ValueError):
            refreshed = None
        if refreshed is not None and refreshed.page_count:
            return refreshed.profile
        if created:
            with Session(self.engine) as session, session.begin():
                profile = session.get(WikiProfile, profile_id)
                if profile is not None:
                    session.delete(profile)
        return None

    async def _fetch_sitemap(
        self, sitemap_url: str, policy: AcquisitionPolicy
    ) -> SitemapDocument:
        if self.acquisition is None:
            raise RuntimeError("wiki inventory requires an acquisition service")
        final_url, response = await self.acquisition.fetch_http(sitemap_url, policy)
        return parse_sitemap_xml(response.body, final_url)

    async def refresh_inventory(
        self, profile_id: str, policy: AcquisitionPolicy
    ) -> WikiInventoryRefresh:
        """Reuse a fresh cache or safely replace the profile's same-host inventory."""

        now = self.clock()
        with Session(self.engine) as session:
            profile = session.get(WikiProfile, profile_id)
            if profile is None:
                raise LookupError(profile_id)
            fresh = self._is_fresh(profile, now, policy.freshness_seconds)
            page_count = session.scalar(
                select(func.count())
                .select_from(WikiInventoryPage)
                .where(
                    WikiInventoryPage.profile_id == profile_id,
                    WikiInventoryPage.active.is_(True),
                )
            )
            if fresh and page_count:
                return WikiInventoryRefresh(
                    _profile_record(profile), True, int(page_count)
                )
            sitemap_url = profile.sitemap_url
        document = await self._fetch_sitemap(sitemap_url, policy)
        entries = list(document.page_entries)
        for index_url in document.sitemap_urls[:_MAX_SITEMAP_INDEXES]:
            child = await self._fetch_sitemap(index_url, policy)
            entries.extend(child.page_entries)
        same_host = urlsplit(sitemap_url).hostname
        validated: dict[str, SitemapEntry] = {}
        if self.acquisition is None:
            raise RuntimeError("wiki inventory requires an acquisition service")
        for entry in sorted(entries, key=lambda item: item.canonical_url):
            if len(validated) >= _MAX_INVENTORY_PAGES:
                break
            if urlsplit(entry.canonical_url).hostname != same_host:
                continue
            try:
                canonical = await self.acquisition.validate_url(
                    entry.canonical_url, policy
                )
            except (TypeError, ValueError):
                continue
            if urlsplit(canonical).hostname == same_host:
                validated.setdefault(
                    canonical, SitemapEntry(canonical, entry.last_modified)
                )
        with Session(self.engine) as session, session.begin():
            profile = session.get(WikiProfile, profile_id)
            if profile is None:
                raise LookupError(profile_id)
            session.execute(
                update(WikiInventoryPage)
                .where(WikiInventoryPage.profile_id == profile_id)
                .values(active=False)
            )
            for entry in validated.values():
                page = session.scalar(
                    select(WikiInventoryPage).where(
                        WikiInventoryPage.profile_id == profile_id,
                        WikiInventoryPage.canonical_url == entry.canonical_url,
                    )
                )
                if page is None:
                    title, aliases, section_terms = _inventory_metadata(
                        entry.canonical_url
                    )
                    page = WikiInventoryPage(
                        id=_stable_id("wiki-page", profile_id, entry.canonical_url),
                        profile_id=profile_id,
                        canonical_url=entry.canonical_url,
                        title=title,
                        aliases_json=aliases,
                        section_terms_json=section_terms,
                        active=True,
                        last_modified=entry.last_modified,
                        indexed_at=now,
                    )
                    session.add(page)
                else:
                    page.active = True
                    page.last_modified = entry.last_modified
                    page.indexed_at = now
            profile.inventory_fetched_at = now
            return WikiInventoryRefresh(
                _profile_record(profile), False, len(validated)
            )

    def select_and_enqueue(
        self,
        *,
        profile_id: str,
        workspace_id: str,
        questions: tuple[dict[str, Any], ...],
    ) -> tuple[WikiQueueSelection, ...]:
        """Match title, alias, and section terms with stable URL queue ordering."""

        capacities = {
            str(question["id"]): int(question["source_budget"])
            for question in questions
        }
        question_priorities = {
            str(question["id"]): int(question["priority"]) for question in questions
        }
        remaining = dict(capacities)
        matches: list[tuple[int, int, str, str, WikiInventoryPage]] = []
        with Session(self.engine) as session:
            pages = session.scalars(
                select(WikiInventoryPage)
                .where(
                    WikiInventoryPage.profile_id == profile_id,
                    WikiInventoryPage.active.is_(True),
                )
                .order_by(WikiInventoryPage.canonical_url)
            ).all()
            existing = {
                item.inventory_page_id: item
                for item in session.scalars(
                    select(WikiPageQueue).where(
                        WikiPageQueue.workspace_id == workspace_id
                    )
                ).all()
            }
            for question in questions:
                question_id = str(question["id"])
                for page in pages:
                    prior = existing.get(page.id)
                    if prior is not None and prior.status in _TERMINAL_QUEUE_STATUSES:
                        continue
                    score = _match_score(page, question)
                    if score:
                        matches.append(
                            (
                                int(question["priority"]),
                                -score,
                                page.canonical_url,
                                question_id,
                                page,
                            )
                        )
        selected_by_page: dict[str, dict[str, Any]] = {}
        for priority, negative_score, _url, question_id, page in sorted(matches):
            if remaining.get(question_id, 0) <= 0:
                continue
            remaining[question_id] -= 1
            selection = selected_by_page.setdefault(
                page.id,
                {
                    "page": page,
                    "question_ids": [],
                    "priority": priority,
                    "score": -negative_score,
                },
            )
            selection["question_ids"].append(question_id)
            selection["priority"] = min(int(selection["priority"]), priority)
            selection["score"] = max(int(selection["score"]), -negative_score)
        output: list[WikiQueueSelection] = []
        with Session(self.engine) as session, session.begin():
            for value in sorted(
                selected_by_page.values(),
                key=lambda item: (
                    int(item["priority"]),
                    -int(item["score"]),
                    item["page"].canonical_url,
                ),
            ):
                page = value["page"]
                question_ids = tuple(
                    sorted(
                        set(value["question_ids"]),
                        key=lambda question_id: (
                            question_priorities.get(question_id, 2**31 - 1),
                            question_id,
                        ),
                    )
                )
                queue = session.scalar(
                    select(WikiPageQueue).where(
                        WikiPageQueue.workspace_id == workspace_id,
                        WikiPageQueue.inventory_page_id == page.id,
                    )
                )
                if queue is None:
                    queue = WikiPageQueue(
                        id=_stable_id("wiki-queue", workspace_id, page.id),
                        workspace_id=workspace_id,
                        inventory_page_id=page.id,
                        question_ids_json=list(question_ids),
                        priority=int(value["priority"]),
                        score=int(value["score"]),
                        status="PENDING",
                        selected_at=self.clock(),
                    )
                    session.add(queue)
                elif queue.status not in _TERMINAL_QUEUE_STATUSES:
                    queue.question_ids_json = sorted(
                        {*queue.question_ids_json, *question_ids},
                        key=lambda question_id: (
                            question_priorities.get(question_id, 2**31 - 1),
                            question_id,
                        ),
                    )
                    queue.priority = min(queue.priority, int(value["priority"]))
                    queue.score = max(queue.score, int(value["score"]))
                output.append(
                    WikiQueueSelection(
                        queue_id=queue.id,
                        inventory_page_id=page.id,
                        canonical_url=page.canonical_url,
                        title=page.title,
                        question_ids=tuple(queue.question_ids_json),
                        priority=queue.priority,
                        score=queue.score,
                    )
                )
        return tuple(output)

    def should_defer_external_work(self, workspace_id: str) -> bool:
        with Session(self.engine) as session:
            pending = session.scalar(
                select(func.count())
                .select_from(WikiPageQueue)
                .where(
                    WikiPageQueue.workspace_id == workspace_id,
                    WikiPageQueue.status.not_in(_TERMINAL_QUEUE_STATUSES),
                )
            )
            return bool(pending)

    def approved_inventory(
        self, profile_id: str | None, *, limit: int = 50
    ) -> list[dict[str, object]]:
        if profile_id is None:
            return []
        with Session(self.engine) as session:
            pages = session.scalars(
                select(WikiInventoryPage)
                .where(
                    WikiInventoryPage.profile_id == profile_id,
                    WikiInventoryPage.active.is_(True),
                )
                .order_by(WikiInventoryPage.title, WikiInventoryPage.canonical_url)
                .limit(limit)
            ).all()
            return [
                {
                    "page_id": page.id,
                    "title": page.title,
                    "aliases": list(page.aliases_json),
                    "section_terms": list(page.section_terms_json),
                }
                for page in pages
            ]

    def mark_queue_terminal(self, statuses: dict[str, str]) -> None:
        invalid = set(statuses.values()) - _TERMINAL_QUEUE_STATUSES
        if invalid:
            raise ValueError("wiki queue status must be terminal")
        with Session(self.engine) as session, session.begin():
            for queue_id, status in statuses.items():
                queue = session.get(WikiPageQueue, queue_id)
                if queue is not None:
                    queue.status = status
