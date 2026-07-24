from __future__ import annotations

import asyncio

import httpx
import pytest

from app.v2.acquisition import HttpxTransport, NonSuccessResponseError
from app.v2.providers import (
    ErrorClass,
    GeminiAdapter,
    GenericOpenAIAdapter,
    ModelRequest,
    OpenAIAdapter,
    ProviderError,
)
from app.v2.search import DuckDuckGoSearch, SearchBlockedError


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
@pytest.mark.parametrize(
    ("status", "body", "error_class"),
    [
        (401, {}, ErrorClass.AUTH),
        (429, {}, ErrorClass.RATE_LIMIT),
        (500, {}, ErrorClass.TRANSIENT),
        (400, {"error": {"message": "maximum context length"}}, ErrorClass.CONTEXT),
        (400, {"error": {"message": "tools are not supported"}}, ErrorClass.CAPABILITY),
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
