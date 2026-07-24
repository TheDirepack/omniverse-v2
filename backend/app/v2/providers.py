from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any, Protocol

import httpx
from pydantic import Field

from app.v2.contracts import Contract


class AdapterKind(str, Enum):
    GEMINI = "GEMINI"
    OPENAI = "OPENAI"
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"


class ErrorClass(str, Enum):
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    TRANSIENT = "TRANSIENT"
    CAPABILITY = "CAPABILITY"
    CONTEXT = "CONTEXT"
    INPUT = "INPUT"
    INTERNAL = "INTERNAL"


class ProviderError(RuntimeError):
    def __init__(
        self, error_class: ErrorClass, message: str, *, retry_after: int | None = None
    ) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.retry_after = retry_after


class ModelRequest(Contract):
    model: str
    messages: tuple[dict[str, Any], ...]
    tools: tuple[dict[str, Any], ...] = ()
    max_output_tokens: int | None = Field(default=None, gt=0)
    structured_schema: dict[str, Any] | None = None


class ToolCall(Contract):
    id: str
    name: str
    arguments: dict[str, Any]


class Usage(Contract):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ModelResponse(Contract):
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: Usage
    finish_reason: str | None = None
    response_id: str | None = None
    provider_id: str | None = None
    model_id: str | None = None


class ProviderAdapter(Protocol):
    kind: AdapterKind

    async def complete(
        self, request: ModelRequest, credential: str
    ) -> ModelResponse: ...


InjectedCall = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]


def _error_from_response(response: httpx.Response) -> ProviderError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    message = str(
        body.get("error", {}).get("message") or response.text or "provider error"
    )
    lowered = message.casefold()
    if response.status_code in {401, 403}:
        error_class = ErrorClass.AUTH
    elif response.status_code == 429:
        error_class = ErrorClass.RATE_LIMIT
    elif response.status_code >= 500:
        error_class = ErrorClass.TRANSIENT
    elif response.status_code == 400 and any(
        value in lowered
        for value in ("context length", "maximum context", "too many tokens")
    ):
        error_class = ErrorClass.CONTEXT
    elif response.status_code == 400 and any(
        value in lowered for value in ("not supported", "unsupported", "capability")
    ):
        error_class = ErrorClass.CAPABILITY
    else:
        error_class = ErrorClass.INPUT
    retry_header = response.headers.get("retry-after")
    try:
        retry_after = int(float(retry_header)) if retry_header is not None else None
    except ValueError:
        retry_after = None
    return ProviderError(error_class, message, retry_after=retry_after)


async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    try:
        response = await client.post(
            url, json=payload, headers=headers, timeout=timeout
        )
    except httpx.TimeoutException as error:
        raise ProviderError(
            ErrorClass.TRANSIENT, "provider request timed out"
        ) from error
    except httpx.NetworkError as error:
        raise ProviderError(ErrorClass.TRANSIENT, "provider network failure") from error
    if not 200 <= response.status_code < 300:
        raise _error_from_response(response)
    try:
        return response.json()
    except ValueError as error:
        raise ProviderError(
            ErrorClass.TRANSIENT, "provider returned invalid JSON"
        ) from error


def _openai_response(payload: dict[str, Any]) -> ModelResponse:
    choice = payload.get("choices", [{}])[0]
    message = choice.get("message", {})
    calls = tuple(
        ToolCall(
            id=call.get("id", ""),
            name=call.get("function", {}).get("name", ""),
            arguments=json.loads(call.get("function", {}).get("arguments", "{}")),
        )
        for call in message.get("tool_calls", ())
    )
    usage = payload.get("usage", {})
    input_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = int(usage.get("completion_tokens", 0))
    return ModelResponse(
        text=message.get("content") or "",
        tool_calls=calls,
        usage=Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        finish_reason=choice.get("finish_reason"),
        response_id=payload.get("id"),
        provider_id="openai",
        model_id=payload.get("model"),
    )


class OpenAIAdapter:
    kind = AdapterKind.OPENAI

    def __init__(
        self,
        call: InjectedCall | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.openai.com",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._call = call
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def complete(self, request: ModelRequest, credential: str) -> ModelResponse:
        if self._call is not None:
            return _openai_response(
                await self._call(request.model_dump(exclude_none=True), credential)
            )
        if self.client is None:
            raise ProviderError(ErrorClass.INTERNAL, "HTTP client is not configured")
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": list(request.messages),
        }
        if request.tools:
            payload["tools"] = list(request.tools)
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        if request.structured_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": request.structured_schema,
                },
            }
        raw = await _post_json(
            self.client,
            self._url(),
            payload,
            {
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
            },
            self.timeout_seconds,
        )
        return _openai_response(raw)

    def _url(self) -> str:
        suffix = "/chat/completions"
        if self.kind is AdapterKind.OPENAI and not self.base_url.endswith("/v1"):
            suffix = "/v1/chat/completions"
        return f"{self.base_url}{suffix}"


class GenericOpenAIAdapter(OpenAIAdapter):
    kind = AdapterKind.OPENAI_COMPATIBLE


class GeminiAdapter:
    kind = AdapterKind.GEMINI

    def __init__(
        self,
        call: InjectedCall | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._call = call
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def complete(self, request: ModelRequest, credential: str) -> ModelResponse:
        if self._call is not None:
            raw = await self._call(request.model_dump(exclude_none=True), credential)
        else:
            if self.client is None:
                raise ProviderError(
                    ErrorClass.INTERNAL, "HTTP client is not configured"
                )
            system_parts = [
                {"text": str(message.get("content", ""))}
                for message in request.messages
                if message.get("role") == "system"
            ]
            payload: dict[str, Any] = {
                "contents": [
                    {
                        "role": (
                            "model" if message.get("role") == "assistant" else "user"
                        ),
                        "parts": [{"text": str(message.get("content", ""))}],
                    }
                    for message in request.messages
                    if message.get("role") != "system"
                ]
            }
            if system_parts:
                payload["systemInstruction"] = {"parts": system_parts}
            generation: dict[str, Any] = {}
            if request.max_output_tokens is not None:
                generation["maxOutputTokens"] = request.max_output_tokens
            if request.structured_schema is not None:
                generation.update(
                    responseMimeType="application/json",
                    responseSchema=request.structured_schema,
                )
            if generation:
                payload["generationConfig"] = generation
            declarations = [tool.get("function", tool) for tool in request.tools]
            if declarations:
                payload["tools"] = [{"functionDeclarations": declarations}]
            raw = await _post_json(
                self.client,
                f"{self.base_url}/models/{request.model}:generateContent?key={credential}",
                payload,
                {"Content-Type": "application/json"},
                self.timeout_seconds,
            )
        candidate = raw.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", ())
        text = "".join(part.get("text", "") for part in parts)
        calls = tuple(
            ToolCall(
                id=part.get("id", ""),
                name=part["functionCall"]["name"],
                arguments=part["functionCall"].get("args", {}),
            )
            for part in parts
            if "functionCall" in part
        )
        usage = raw.get("usageMetadata", {})
        input_tokens = int(usage.get("promptTokenCount", 0))
        output_tokens = int(usage.get("candidatesTokenCount", 0))
        return ModelResponse(
            text=text,
            tool_calls=calls,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            finish_reason=candidate.get("finishReason"),
            response_id=raw.get("responseId"),
            provider_id="gemini",
            model_id=raw.get("modelVersion"),
        )
