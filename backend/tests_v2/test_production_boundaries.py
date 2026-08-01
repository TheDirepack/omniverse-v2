from __future__ import annotations

import asyncio

import httpx
import pytest

from app.v2.acquisition import (
    AcquisitionPolicy,
    BrowserResult,
    HttpxTransport,
    NonSuccessResponseError,
)
from app.v2.contracts import PlannerOutput
from app.v2.providers import (
    ErrorClass,
    GeminiAdapter,
    GenericOpenAIAdapter,
    ModelRequest,
    OpenAIAdapter,
    ProviderError,
)
from app.v2.search import (
    BingBrowserSearch,
    BraveApiSearch,
    CachedFallbackSearch,
    DuckDuckGoSearch,
    GoogleBrowserSearch,
    SearchBlockedError,
    SearchTransientError,
)


def _request() -> ModelRequest:
    return ModelRequest(
        model="model-x",
        messages=({"role": "user", "content": "hello"},),
        tools=({"type": "function", "function": {"name": "lookup"}},),
        max_output_tokens=123,
        structured_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("factory", "expected_path"),
    [
        (OpenAIAdapter, "/v1/chat/completions"),
        (GenericOpenAIAdapter, "/v1/chat/completions"),
    ],
)
async def test_openai_http_payload_translation(factory, expected_path: str) -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers["authorization"]
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    base = (
        "https://api.openai.com"
        if factory is OpenAIAdapter
        else "https://local.test/v1"
    )
    result = await factory(client=client, base_url=base, timeout_seconds=4).complete(
        _request(), "secret"
    )
    assert result.text == "ok"
    assert seen["path"] == expected_path
    assert seen["auth"] == "Bearer secret"
    payload = seen["json"]
    assert payload["max_tokens"] == 123
    assert payload["response_format"]["type"] == "json_schema"
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_payload_translation() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await GeminiAdapter(client=client).complete(_request(), "gem-key")
    assert "models/model-x:generateContent?key=gem-key" in seen["url"]
    assert seen["json"]["generationConfig"]["maxOutputTokens"] == 123
    assert seen["json"]["generationConfig"]["responseMimeType"] == "application/json"
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_inlines_and_sanitizes_planner_schema() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = __import__("json").loads(request.content)
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        )

    request = _request().model_copy(
        update={"structured_schema": PlannerOutput.model_json_schema()}
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await GeminiAdapter(client=client).complete(request, "gem-key")

    schema = seen["json"]["generationConfig"]["responseSchema"]
    serialized = __import__("json").dumps(schema)
    assert "$defs" not in serialized
    assert "$ref" not in serialized
    assert "additionalProperties" not in serialized
    assert "exclusiveMinimum" not in serialized
    question = schema["properties"]["questions"]["items"]
    assert question["type"] == "object"
    assert set(question["required"]) == {
        "id",
        "priority",
        "question",
        "queries",
        "source_budget",
        "stop_conditions",
    }
    assert question["properties"]["source_budget"]["minimum"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_structured_schema_rejection_is_capability_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "provider rejected response schema"}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        await GeminiAdapter(client=client).complete(_request(), "gem-key")

    assert caught.value.error_class is ErrorClass.CAPABILITY
    assert caught.value.status == 400
    await client.aclose()


@pytest.mark.asyncio
async def test_gemini_retired_model_is_capability_failure() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": {
                    "message": "This model is no longer available to new users."
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        await GeminiAdapter(client=client).complete(_request(), "gem-key")

    assert caught.value.error_class is ErrorClass.CAPABILITY
    assert caught.value.status == 404
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "error_class"),
    [
        (401, {}, ErrorClass.AUTH),
        (429, {}, ErrorClass.RATE_LIMIT),
        (500, {}, ErrorClass.TRANSIENT),
        (
            400,
            {
                "error": {
                    "message": "opaque context error",
                    "metadata": {"error_type": "context_length_exceeded"},
                }
            },
            ErrorClass.CONTEXT,
        ),
        (
            400,
            {
                "error": {
                    "message": "opaque request error",
                    "metadata": {"error_type": "invalid_request"},
                }
            },
            ErrorClass.INPUT,
        ),
    ],
)
@pytest.mark.evaluation
async def test_model_http_errors_are_stable(status, body, error_class) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"retry-after": "7"}, json=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAIAdapter(client=client)
    with pytest.raises(ProviderError) as caught:
        await adapter.complete(_request(), "secret")
    assert caught.value.error_class is error_class
    if status == 429:
        assert caught.value.retry_after == 7
    await client.aclose()


@pytest.mark.asyncio
async def test_streaming_transport_rejects_non_2xx_and_enforces_byte_limit() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(404, content=b"no")
        )
    )
    with pytest.raises(NonSuccessResponseError):
        await HttpxTransport(client).get(
            "https://example.test", timeout_seconds=1, max_bytes=10
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_streaming_transport_returns_redirect_for_service_revalidation() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                302, headers={"location": "https://next.test/"}
            )
        )
    )
    response = await HttpxTransport(client).get(
        "https://example.test", timeout_seconds=1, max_bytes=10
    )
    assert response.status == 302
    assert response.headers["location"] == "https://next.test/"
    await client.aclose()


@pytest.mark.asyncio
async def test_streaming_transport_enforces_total_wall_clock_deadline() -> None:
    async def slow(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.02)
        return httpx.Response(200, content=b"ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow))
    with pytest.raises(TimeoutError):
        await HttpxTransport(client).get(
            "https://example.test", timeout_seconds=0.001, max_bytes=10
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_duckduckgo_html_search_parses_canonical_bounded_results() -> None:
    html = (
        b'<a class="result__a" href="//duckduckgo.com/l/?uddg='
        b'https%3A%2F%2FExample.test%2Fa">Title</a>'
        b'<a class="result__snippet">Snippet</a>'
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=html)
        )
    )
    values = await DuckDuckGoSearch(client).search("query", limit=1)
    assert len(values) == 1
    assert values[0].canonical_url == "https://example.test/a"
    assert values[0].title == "Title"
    await client.aclose()


@pytest.mark.asyncio
async def test_duckduckgo_blocked_response_is_typed() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(202, content=b"captcha")
        )
    )
    with pytest.raises(SearchBlockedError):
        await DuckDuckGoSearch(client).search("query", limit=1)
    await client.aclose()


@pytest.mark.asyncio
async def test_cached_fallback_search_uses_next_provider_after_typed_failure() -> None:
    class BlockedSearch:
        async def search(self, query: str, *, limit: int):
            del query, limit
            raise SearchBlockedError("blocked")

    class SuccessfulSearch:
        calls = 0

        async def search(self, query: str, *, limit: int):
            del limit
            self.calls += 1
            return ({"url": "https://example.test/result", "title": query},)

    fallback = SuccessfulSearch()
    search = CachedFallbackSearch((BlockedSearch(), fallback))

    assert await search.search("secret query", limit=2) == (
        {"url": "https://example.test/result", "title": "secret query"},
    )
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_cached_fallback_search_caches_successes_and_expires_entries() -> None:
    class CountingSearch:
        calls = 0

        async def search(self, query: str, *, limit: int):
            self.calls += 1
            return (f"{query}:{limit}:{self.calls}",)

    now = [10.0]
    provider = CountingSearch()
    search = CachedFallbackSearch(
        (provider,), ttl_seconds=5, max_entries=1, clock=lambda: now[0]
    )

    assert await search.search("one", limit=1) == ("one:1:1",)
    assert await search.search("one", limit=1) == ("one:1:1",)
    now[0] += 6
    assert await search.search("one", limit=1) == ("one:1:2",)
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_cached_fallback_search_evicts_lru_and_does_not_cache_errors() -> None:
    class ControlledSearch:
        calls = 0

        async def search(self, query: str, *, limit: int):
            del limit
            self.calls += 1
            if query == "error":
                raise SearchTransientError("temporary")
            return (f"{query}:{self.calls}",)

    provider = ControlledSearch()
    search = CachedFallbackSearch((provider,), max_entries=1)

    assert await search.search("one", limit=1) == ("one:1",)
    assert await search.search("two", limit=1) == ("two:2",)
    assert await search.search("one", limit=1) == ("one:3",)
    with pytest.raises(SearchTransientError):
        await search.search("error", limit=1)
    with pytest.raises(SearchTransientError):
        await search.search("error", limit=1)
    assert provider.calls == 5


@pytest.mark.asyncio
async def test_cached_fallback_search_shuffles_free_providers_before_final_chain(
) -> None:
    calls: list[str] = []

    class Provider:
        def __init__(self, name: str) -> None:
            self.name = name

        async def search(self, query: str, *, limit: int):
            del query, limit
            calls.append(self.name)
            raise SearchTransientError("unavailable")

    first, second, paid = Provider("first"), Provider("second"), Provider("paid")
    search = CachedFallbackSearch(
        (first, second),
        final_providers=(paid,),
        shuffle_alternates=lambda providers: tuple(reversed(providers)),
    )

    with pytest.raises(SearchTransientError):
        await search.search("query", limit=1)

    assert calls == ["second", "first", "paid"]


class _BrowserSearch:
    def __init__(self, html: str) -> None:
        self.html = html
        self.calls: list[tuple[str, AcquisitionPolicy]] = []

    async def acquire(self, url: str, policy: AcquisitionPolicy) -> BrowserResult:
        self.calls.append((url, policy))
        return BrowserResult(
            body=self.html.encode(), final_url=url, content_type="text/html"
        )


@pytest.mark.asyncio
async def test_google_browser_search_parses_external_results_and_uses_search_timeout(
) -> None:
    browser = _BrowserSearch(
        '<div id="search"><a href="/url?url=https%3A%2F%2Fexample.test%2Ffact">'
        "Example fact</a><div>Supported snippet</div></div>"
    )
    search = GoogleBrowserSearch(
        browser, AcquisitionPolicy(timeout_seconds=45, max_body_bytes=100_000)
    )

    values = await search.search("secret query", limit=2)

    assert [(value.canonical_url, value.title) for value in values] == [
        ("https://example.test/fact", "Example fact")
    ]
    assert browser.calls[0][1].timeout_seconds == 45
    assert "secret+query" in browser.calls[0][0]


@pytest.mark.asyncio
async def test_bing_browser_search_parses_ranked_results() -> None:
    browser = _BrowserSearch(
        '<li class="b_algo"><h2><a href="https://example.test/fact">Fact</a></h2>'
        '<div class="b_caption"><p>Supported snippet</p></div></li>'
    )
    search = BingBrowserSearch(browser, AcquisitionPolicy(max_body_bytes=100_000))

    values = await search.search("query", limit=1)

    assert [(value.canonical_url, value.snippet) for value in values] == [
        ("https://example.test/fact", "Supported snippet")
    ]


@pytest.mark.asyncio
async def test_browser_search_classifies_challenge_without_bypassing_it() -> None:
    browser = _BrowserSearch("<title>Verify you are human</title><p>CAPTCHA</p>")
    search = GoogleBrowserSearch(browser, AcquisitionPolicy(max_body_bytes=100_000))

    with pytest.raises(SearchBlockedError):
        await search.search("query", limit=1)


@pytest.mark.asyncio
async def test_brave_api_search_uses_subscription_header_only_when_key_is_available(
) -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://example.test/fact",
                            "title": "Fact",
                            "description": "Supported snippet",
                        }
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    search = BraveApiSearch(client, credential_getter=lambda: "brave-secret")

    values = await search.search("query", limit=1)

    assert values[0].canonical_url == "https://example.test/fact"
    assert seen["headers"]["x-subscription-token"] == "brave-secret"
    assert "brave-secret" not in seen["url"]
    await client.aclose()
