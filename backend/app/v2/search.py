# Search boundary errors intentionally carry stable provider diagnostics.
# ruff: noqa: SIM105, TRY003

from __future__ import annotations

import asyncio
import hashlib
import inspect
from collections import OrderedDict
from dataclasses import dataclass
from random import SystemRandom
from time import monotonic
from typing import Any, Callable, Protocol
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.v2.acquisition import AcquisitionPolicy, BrowserResult, canonicalize_url
from app.v2.logging import redact
from app.v2.preprocessing import preprocess_document


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    canonical_url: str
    title: str
    snippet: str
    rank: int
    source_class: str = "SECONDARY"
    publisher: str | None = None
    lineage_id: str | None = None


class SearchProvider(Protocol):
    async def search(self, query: str, *, limit: int) -> tuple[Any, ...]: ...


class SearchError(RuntimeError):
    pass


class SearchTransientError(SearchError):
    pass


class SearchBlockedError(SearchError):
    pass


class CachedFallbackSearch:
    """Retries typed provider failures and caches successful search results."""

    def __init__(
        self,
        providers: tuple[SearchProvider, ...],
        *,
        final_providers: tuple[SearchProvider, ...] = (),
        ttl_seconds: float = 300,
        max_entries: int = 256,
        clock: Callable[[], float] = monotonic,
        shuffle_alternates: Callable[
            [tuple[SearchProvider, ...]], tuple[SearchProvider, ...]
        ] | None = None,
        logger=None,
    ) -> None:
        if not providers:
            raise ValueError("at least one search provider is required")
        if ttl_seconds <= 0:
            raise ValueError("cache ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("cache max_entries must be positive")
        self.providers = providers
        self.final_providers = final_providers
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.clock = clock
        self.shuffle_alternates = shuffle_alternates or (
            lambda providers: tuple(SystemRandom().sample(providers, len(providers)))
        )
        self.logger = logger
        self._cache: OrderedDict[tuple[str, int], tuple[float, tuple[Any, ...]]] = (
            OrderedDict()
        )
        self._lock = asyncio.Lock()

    def _log(
        self, event_type: str, message: str, *, data=None, **correlation
    ) -> None:
        if self.logger is None:
            return
        try:
            self.logger.log_agent(
                "search",
                event_type,
                message=message,
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

    async def search(
        self, query: str, *, limit: int, **correlation
    ) -> tuple[Any, ...]:
        key = (hashlib.sha256(query.encode()).hexdigest(), limit)
        now = self.clock()
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached[0] > now:
                self._cache.move_to_end(key)
                self._log(
                    "search.cache_hit",
                    "Search cache hit",
                    data={"requested_limit": limit, "result_count": len(cached[1])},
                    **correlation,
                )
                return cached[1]
            if cached is not None:
                del self._cache[key]
        self._log(
            "search.cache_miss",
            "Search cache miss",
            data={"requested_limit": limit},
            **correlation,
        )
        last_error: SearchError | None = None
        providers = (*self.shuffle_alternates(self.providers), *self.final_providers)
        for index, provider in enumerate(providers):
            try:
                values = tuple(
                    await self._call_provider(provider, query, limit, correlation)
                )
            except SearchError as error:
                last_error = error
                if index + 1 < len(providers):
                    self._log(
                        "search.provider_fallback",
                        "Search provider failed; trying fallback",
                        data={"provider_index": index},
                        **correlation,
                    )
                continue
            async with self._lock:
                self._cache[key] = (self.clock() + self.ttl_seconds, values)
                self._cache.move_to_end(key)
                while len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)
            return values
        assert last_error is not None
        raise last_error

    @staticmethod
    async def _call_provider(
        provider: SearchProvider,
        query: str,
        limit: int,
        correlation: dict[str, Any],
    ) -> tuple[Any, ...]:
        search = provider.search
        parameters = inspect.signature(search).parameters
        if "run_id" in parameters or any(
            item.kind is inspect.Parameter.VAR_KEYWORD
            for item in parameters.values()
        ):
            return await search(query, limit=limit, **correlation)
        return await search(query, limit=limit)


class BrowserHtmlSearch:
    provider_name = "browser"
    base_url = ""

    def __init__(
        self,
        browser,
        policy: AcquisitionPolicy,
        *,
        logger=None,
    ) -> None:
        self.browser = browser
        self.policy = policy
        self.logger = logger

    def _log(
        self, event_type: str, message: str, *, data=None, **correlation
    ) -> None:
        if self.logger is None:
            return
        try:
            self.logger.log_agent(
                "search",
                event_type,
                message=message,
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

    def _search_url(self, query: str) -> str:
        return f"{self.base_url}?{urlencode({'q': query})}"

    def _result_nodes(self, soup: BeautifulSoup):
        raise NotImplementedError

    def _candidate_url(self, raw_url: str) -> str | None:
        parsed = urlsplit(urljoin(self.base_url, raw_url))
        if parsed.hostname == urlsplit(self.base_url).hostname:
            return None
        try:
            return canonicalize_url(parsed.geturl())
        except (TypeError, ValueError):
            return None

    async def search(
        self, query: str, *, limit: int, **correlation
    ) -> tuple[SearchCandidate, ...]:
        bounded = max(0, limit)
        started = monotonic()
        data = {
            "provider": self.provider_name,
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "query_length": len(query),
            "requested_limit": limit,
            "timeout_seconds": self.policy.timeout_seconds,
        }
        if bounded == 0:
            return ()
        try:
            rendered: BrowserResult = await self.browser.acquire(
                self._search_url(query), self.policy
            )
        except Exception as error:
            self._log(
                "search.failed",
                "Browser search failed",
                data={
                    **data,
                    "stage": "navigate",
                    "duration_ms": (monotonic() - started) * 1000,
                    "error_class": type(error).__name__,
                },
                **correlation,
            )
            raise SearchTransientError("browser search navigation failed") from error
        soup = BeautifulSoup(rendered.body, "html.parser")
        page_text = soup.get_text(" ", strip=True).casefold()
        if any(
            phrase in page_text
            for phrase in (
                "captcha",
                "verify you are human",
                "unusual traffic",
                "security check",
            )
        ):
            self._log(
                "search.failed",
                "Browser search challenge detected",
                data={
                    **data,
                    "stage": "challenge_detection",
                    "duration_ms": (monotonic() - started) * 1000,
                    "error_class": "SearchBlockedError",
                },
                **correlation,
            )
            raise SearchBlockedError("browser search challenge detected")
        values: list[SearchCandidate] = []
        for anchor, title, snippet in self._result_nodes(soup):
            url = self._candidate_url(str(anchor.get("href") or ""))
            if url is None:
                continue
            values.append(
                SearchCandidate(
                    canonical_url=url,
                    title=title,
                    snippet=snippet,
                    rank=len(values) + 1,
                )
            )
            if len(values) >= bounded:
                break
        result = normalize_candidates(tuple(values), bounded)
        self._log(
            "search.succeeded",
            "Browser search succeeded",
            data={
                **data,
                "stage": "parse",
                "duration_ms": (monotonic() - started) * 1000,
                "result_count": len(result),
            },
            **correlation,
        )
        return result


class GoogleBrowserSearch(BrowserHtmlSearch):
    provider_name = "google"
    base_url = "https://www.google.com/search"

    def _candidate_url(self, raw_url: str) -> str | None:
        parsed = urlsplit(raw_url)
        if parsed.path == "/url":
            raw_url = parse_qs(parsed.query).get("url", [raw_url])[0]
        return super()._candidate_url(raw_url)

    def _result_nodes(self, soup: BeautifulSoup):
        for anchor in soup.select("#search a[href]"):
            title = anchor.get_text(" ", strip=True)
            if not title:
                continue
            parent = anchor.find_parent(["div", "article"])
            snippet = parent.get_text(" ", strip=True) if parent else ""
            yield anchor, title, snippet


class BingBrowserSearch(BrowserHtmlSearch):
    provider_name = "bing"
    base_url = "https://www.bing.com/search"

    def _result_nodes(self, soup: BeautifulSoup):
        for result in soup.select("li.b_algo"):
            anchor = result.select_one("h2 a[href]")
            if anchor is None:
                continue
            snippet = result.select_one(".b_caption p")
            yield (
                anchor,
                anchor.get_text(" ", strip=True),
                snippet.get_text(" ", strip=True) if snippet else "",
            )


class BraveBrowserSearch(BrowserHtmlSearch):
    provider_name = "brave"
    base_url = "https://search.brave.com/search"

    def _result_nodes(self, soup: BeautifulSoup):
        for result in soup.select(".snippet, .result, [data-type='web']"):
            anchor = result.select_one("a[href]")
            if anchor is None:
                continue
            title = anchor.get_text(" ", strip=True)
            if title:
                yield anchor, title, result.get_text(" ", strip=True)


class BraveApiSearch:
    provider_name = "brave_api"
    base_url = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self, client: httpx.AsyncClient, *, credential_getter, logger=None
    ) -> None:
        self.client = client
        self.credential_getter = credential_getter
        self.logger = logger

    async def search(
        self, query: str, *, limit: int, **_correlation
    ) -> tuple[SearchCandidate, ...]:
        key = self.credential_getter()
        if not key:
            raise SearchTransientError("Brave Search API is not configured")
        try:
            response = await self.client.get(
                self.base_url,
                params={"q": query, "count": max(1, limit)},
                headers={"X-Subscription-Token": key},
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise SearchTransientError("Brave Search API request failed") from error
        except (httpx.NetworkError, httpx.TimeoutException) as error:
            raise SearchTransientError("Brave Search API request failed") from error
        results = response.json().get("web", {}).get("results", [])
        values = tuple(
            SearchCandidate(
                canonical_url=canonicalize_url(str(value["url"])),
                title=str(value.get("title", "")),
                snippet=str(value.get("description", "")),
                rank=index,
            )
            for index, value in enumerate(results[:limit], 1)
            if isinstance(value, dict) and value.get("url")
        )
        return normalize_candidates(values, limit)


class DuckDuckGoSearch:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://html.duckduckgo.com/html/",
        timeout_seconds: float = 15.0,
        max_results: int = 20,
        logger=None,
    ) -> None:
        self.client = client
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self.logger = logger

    def _log(
        self, event_type: str, message: str, *, level="INFO", data=None, **correlation
    ) -> None:
        if self.logger is None:
            return
        try:
            self.logger.log_agent(
                "search",
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

    async def search(
        self,
        query: str,
        *,
        limit: int,
        run_id: str | None = None,
        target_id: str | None = None,
        step_id: str | None = None,
        world_id: str | None = None,
        attempt_number: int | None = None,
        step_kind: str | None = None,
    ) -> tuple[SearchCandidate, ...]:
        bounded = min(max(limit, 0), self.max_results)
        started = monotonic()
        correlation = {
            "run_id": run_id,
            "target_id": target_id,
            "step_id": step_id,
            "world_id": world_id,
            "attempt_number": attempt_number,
            "step_kind": step_kind,
        }
        event_data = {
            "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
            "query_length": len(query),
            "requested_limit": limit,
            "bounded_limit": bounded,
        }
        self._log("search.started", "Search started", data=event_data, **correlation)
        if bounded == 0:
            self._log(
                "search.succeeded",
                "Search succeeded",
                data={**event_data, "result_count": 0, "duration_ms": 0},
                **correlation,
            )
            return ()
        try:
            response = await self.client.get(
                self.base_url,
                params={"q": query},
                follow_redirects=False,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "OmniverseV2/2.0"},
            )
        except (httpx.NetworkError, httpx.TimeoutException) as error:
            self._log(
                "search.failed",
                "Search failed",
                level="ERROR",
                data={
                    **event_data,
                    "duration_ms": (monotonic() - started) * 1000,
                    "error_class": type(error).__name__,
                },
                **correlation,
            )
            raise SearchTransientError("DuckDuckGo request failed") from error
        if response.status_code in {202, 403, 429}:
            self._log(
                "search.failed",
                "Search was blocked",
                level="ERROR",
                data={
                    **event_data,
                    "duration_ms": (monotonic() - started) * 1000,
                    "status": response.status_code,
                    "error_class": "SearchBlockedError",
                },
                **correlation,
            )
            raise SearchBlockedError("DuckDuckGo blocked automated search")
        if not 200 <= response.status_code < 300:
            self._log(
                "search.failed",
                "Search failed",
                level="ERROR",
                data={
                    **event_data,
                    "duration_ms": (monotonic() - started) * 1000,
                    "status": response.status_code,
                    "error_class": "SearchTransientError",
                },
                **correlation,
            )
            raise SearchTransientError(
                f"DuckDuckGo returned HTTP {response.status_code}"
            )
        soup = BeautifulSoup(response.content, "html.parser")
        values: list[SearchCandidate] = []
        for anchor in soup.select("a.result__a"):
            raw_url = str(anchor.get("href") or "")
            parsed = urlsplit(raw_url)
            if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
                raw_url = unquote(parse_qs(parsed.query).get("uddg", [raw_url])[0])
            snippet_node = anchor.find_next(class_="result__snippet")
            try:
                url = canonicalize_url(raw_url)
            except (ValueError, TypeError):
                continue
            values.append(
                SearchCandidate(
                    canonical_url=url,
                    title=anchor.get_text(" ", strip=True),
                    snippet=(
                        snippet_node.get_text(" ", strip=True) if snippet_node else ""
                    ),
                    rank=len(values) + 1,
                )
            )
            if len(values) >= bounded:
                break
        result = normalize_candidates(tuple(values), bounded)
        self._log(
            "search.succeeded",
            "Search succeeded",
            data={
                **event_data,
                "duration_ms": (monotonic() - started) * 1000,
                "status": response.status_code,
                "result_count": len(result),
            },
            **correlation,
        )
        return result


def normalize_candidates(
    values: tuple[Any, ...], limit: int
) -> tuple[SearchCandidate, ...]:
    normalized: dict[str, SearchCandidate] = {}
    for fallback_rank, value in enumerate(values[:limit], 1):
        if isinstance(value, SearchCandidate):
            raw = {
                "canonical_url": value.canonical_url,
                "title": value.title,
                "snippet": value.snippet,
                "rank": value.rank,
                "source_class": value.source_class,
                "publisher": value.publisher,
                "lineage_id": value.lineage_id,
            }
        else:
            raw = value if isinstance(value, dict) else vars(value)
        url = canonicalize_url(str(raw.get("canonical_url") or raw["url"]))
        title_source = str(raw.get("title", ""))
        snippet_source = str(raw.get("snippet", ""))
        title = preprocess_document(title_source, "text/plain").cleaned_text
        snippet = preprocess_document(snippet_source, "text/plain").cleaned_text
        candidate = SearchCandidate(
            canonical_url=url,
            title=title or title_source.strip(),
            snippet=snippet or snippet_source.strip(),
            rank=int(raw.get("rank", fallback_rank)),
            source_class=str(raw.get("source_class") or "SECONDARY").upper(),
            publisher=raw.get("publisher"),
            lineage_id=raw.get("lineage_id"),
        )
        prior = normalized.get(url)
        if prior is None or candidate.rank < prior.rank:
            normalized[url] = candidate
    return tuple(
        sorted(normalized.values(), key=lambda item: (item.rank, item.canonical_url))
    )
