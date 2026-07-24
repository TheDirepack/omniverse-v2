# Search boundary errors intentionally carry stable provider diagnostics.
# ruff: noqa: TRY003

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.v2.acquisition import canonicalize_url


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


class DuckDuckGoSearch:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str = "https://html.duckduckgo.com/html/",
        timeout_seconds: float = 15.0,
        max_results: int = 20,
    ) -> None:
        self.client = client
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results

    async def search(self, query: str, *, limit: int) -> tuple[SearchCandidate, ...]:
        bounded = min(max(limit, 0), self.max_results)
        if bounded == 0:
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
            raise SearchTransientError("DuckDuckGo request failed") from error
        if response.status_code in {202, 403, 429}:
            raise SearchBlockedError("DuckDuckGo blocked automated search")
        if not 200 <= response.status_code < 300:
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
        return normalize_candidates(tuple(values), bounded)


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
        candidate = SearchCandidate(
            canonical_url=url,
            title=str(raw.get("title", "")).strip(),
            snippet=str(raw.get("snippet", "")).strip(),
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
