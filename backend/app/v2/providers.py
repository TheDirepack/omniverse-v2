from __future__ import annotations

import json
import threading
from collections.abc import Awaitable, Callable
from enum import Enum
from time import monotonic
from typing import Any, Protocol

import httpx
from pydantic import Field

from app.v2.contracts import Contract


class AdapterKind(str, Enum):
    GEMINI = "GEMINI"
    OPENAI = "OPENAI"
    OPENAI_COMPATIBLE = "OPENAI_COMPATIBLE"
    OPENROUTER = "OPENROUTER"


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
        self,
        error_class: ErrorClass,
        message: str,
        *,
        retry_after: int | None = None,
        status: int | None = None,
        error_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.retry_after = retry_after
        self.status = status
        self.error_type = error_type


class CircuitBreakerError(ProviderError):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for provider resilience."""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_requests: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_requests = half_open_requests

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._failure_start_time: float | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if self._failure_start_time is not None:
                    elapsed = monotonic() - self._failure_start_time
                    if elapsed >= self._recovery_timeout:
                        self._state = CircuitBreakerState.HALF_OPEN
                        self._failure_count = 0
                else:
                    return self._state
            return self._state

    def _check_state(self) -> None:
        current = self.state
        if current in {CircuitBreakerState.HALF_OPEN, CircuitBreakerState.CLOSED}:
            self._failure_count = 0

    def allow_request(self) -> bool:
        with self._lock:
            current = self.state
            if current == CircuitBreakerState.CLOSED:
                return True
            if current == CircuitBreakerState.OPEN:
                if self._failure_start_time is not None:
                    elapsed = monotonic() - self._failure_start_time
                    if elapsed >= self._recovery_timeout:
                        self._state = CircuitBreakerState.HALF_OPEN
                        self._failure_count = 0
                        return True
                return False
            # HALF_OPEN: allow one request through
            return True

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.CLOSED
                self._failure_count = 0
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if (
                self._failure_count >= self._failure_threshold
                or self._state == CircuitBreakerState.HALF_OPEN
            ):
                self._state = CircuitBreakerState.OPEN
                self._failure_start_time = monotonic()


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
    returned_reasoning: str | None = None
    reasoning_field: str | None = None


class ProviderAdapter(Protocol):
    kind: AdapterKind

    async def complete(
        self, request: ModelRequest, credential: str
    ) -> ModelResponse: ...


InjectedCall = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]


def _provider_error(
    error_data: dict[str, Any], status: int, *, fallback_message: str = ""
) -> ProviderError:
    message = str(error_data.get("message") or fallback_message or "provider error")
    metadata = error_data.get("metadata")
    error_type = metadata.get("error_type") if isinstance(metadata, dict) else None
    if error_type in {
        "context_length_exceeded",
        "max_tokens_exceeded",
        "token_limit_exceeded",
        "string_too_long",
    }:
        error_class = ErrorClass.CONTEXT
    elif error_type in {"authentication", "permission_denied"} or status in {
        401,
        403,
    }:
        error_class = ErrorClass.AUTH
    elif error_type == "rate_limit_exceeded" or status == 429:
        error_class = ErrorClass.RATE_LIMIT
    elif error_type in {
        "provider_overloaded",
        "provider_unavailable",
        "server",
        "timeout",
        "unmapped",
    } or status in {408, 500, 502, 503, 504}:
        error_class = ErrorClass.TRANSIENT
    else:
        error_class = ErrorClass.INPUT
    return ProviderError(
        error_class,
        message,
        status=status,
        error_type=str(error_type) if error_type is not None else None,
    )


def _error_from_response(response: httpx.Response) -> ProviderError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error_data = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error_data, dict):
        error_data = {}
    error = _provider_error(
        error_data, response.status_code, fallback_message=response.text
    )
    retry_header = response.headers.get("retry-after")
    try:
        retry_after = int(float(retry_header)) if retry_header is not None else None
    except ValueError:
        retry_after = None
    error.retry_after = retry_after
    return error


def _embedded_provider_error(payload: dict[str, Any]) -> ProviderError | None:
    error_data = payload.get("error")
    if not isinstance(error_data, dict):
        choices = payload.get("choices")
        first = choices[0] if isinstance(choices, list) and choices else None
        error_data = first.get("error") if isinstance(first, dict) else None
    if not isinstance(error_data, dict):
        return None
    code = error_data.get("code", 500)
    try:
        status = int(code)
    except (TypeError, ValueError):
        status = 500
    return _provider_error(error_data, status)


def _gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    root = schema

    def resolve(reference: str) -> Any:
        if not reference.startswith("#/"):
            raise ProviderError(
                ErrorClass.CAPABILITY,
                "Gemini structured output requires local schema references",
            )
        value: Any = root
        for part in reference[2:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(value, dict) or key not in value:
                raise ProviderError(
                    ErrorClass.INTERNAL, f"unresolved schema reference: {reference}"
                )
            value = value[key]
        return value

    def transform(value: Any, resolving: frozenset[str]) -> Any:
        if isinstance(value, list):
            return [transform(item, resolving) for item in value]
        if not isinstance(value, dict):
            return value
        reference = value.get("$ref")
        if isinstance(reference, str):
            if reference in resolving:
                raise ProviderError(
                    ErrorClass.CAPABILITY,
                    "Gemini structured output does not support recursive schemas",
                )
            merged = dict(resolve(reference))
            merged.update({key: item for key, item in value.items() if key != "$ref"})
            return transform(merged, resolving | {reference})
        transformed = {
            key: transform(item, resolving)
            for key, item in value.items()
            if key
            not in {
                "$defs",
                "$schema",
                "additionalProperties",
                "exclusiveMaximum",
                "exclusiveMinimum",
            }
        }
        for exclusive, inclusive, adjustment in (
            ("exclusiveMinimum", "minimum", 1),
            ("exclusiveMaximum", "maximum", -1),
        ):
            bound = value.get(exclusive)
            if isinstance(bound, (int, float)) and not isinstance(bound, bool):
                transformed[inclusive] = (
                    bound + adjustment if value.get("type") == "integer" else bound
                )
        return transformed

    return transform(schema, frozenset())


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
    reasoning_field = next(
        (name for name in ("reasoning_content", "reasoning") if message.get(name)),
        None,
    )
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
        returned_reasoning=(str(message[reasoning_field]) if reasoning_field else None),
        reasoning_field=(f"message.{reasoning_field}" if reasoning_field else None),
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

    def _url(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    async def complete(self, request: ModelRequest, credential: str) -> ModelResponse:
        if self._call is not None:
            raw = await self._call(request.model_dump(exclude_none=True), credential)
        else:
            if self.client is None:
                raise ProviderError(
                    ErrorClass.INTERNAL, "HTTP client is not configured"
                )
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
        embedded_error = _embedded_provider_error(raw)
        if embedded_error is not None:
            raise embedded_error
        return _openai_response(raw)

    async def sync_models(self, credential: str) -> list[dict[str, Any]]:
        if self.client is None:
            return []
        url = (
            f"{self.base_url}/v1/models"
            if not self.base_url.endswith("/v1")
            else f"{self.base_url}/models"
        )
        try:
            response = await self.client.get(
                url,
                headers={"Authorization": f"Bearer {credential}"},
                timeout=self.timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", data.get("models", []))
                result = []
                for m in models:
                    mid = m.get("id") or m.get("name")
                    if mid:
                        mid = str(mid)
                        lowered = mid.lower()
                        is_text = not any(
                            p in lowered
                            for p in (
                                "embedding",
                                "embed",
                                "tts",
                                "whisper",
                                "audio",
                                "speech",
                                "moderation",
                                "dall-e",
                                "imagen",
                                "image",
                                "stable-diffusion",
                                "flux",
                            )
                        )
                        supports_tools = not any(
                            p in lowered
                            for p in (
                                "embedding",
                                "embed",
                                "tts",
                                "whisper",
                                "audio",
                                "speech",
                                "moderation",
                                "dall-e",
                                "imagen",
                                "image",
                                "stable-diffusion",
                                "flux",
                            )
                        )
                        if is_text:
                            result.append(
                                {
                                    "id": mid,
                                    "name": m.get("name", mid),
                                    "context_window": m.get("context_window", 128_000),
                                    "output_limit": m.get("max_tokens", 4_000),
                                    "supports_text": is_text,
                                    "supports_tools": supports_tools,
                                    "supports_structured": supports_tools,
                                }
                            )
                return result
        except Exception:
            pass
        return []


class GenericOpenAIAdapter(OpenAIAdapter):
    kind = AdapterKind.OPENAI_COMPATIBLE


class OpenRouterAdapter(OpenAIAdapter):
    kind = AdapterKind.OPENROUTER
    catalog_is_authoritative = True

    def __init__(
        self,
        call: InjectedCall | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://openrouter.ai/api",
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            call,
            client=client,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    async def sync_models(self, credential: str) -> list[dict[str, Any]]:
        if self.client is None:
            raise ProviderError(ErrorClass.INTERNAL, "HTTP client is not configured")
        url = (
            f"{self.base_url}/models/user"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/models/user"
        )
        try:
            response = await self.client.get(
                url,
                headers={"Authorization": f"Bearer {credential}"},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise ProviderError(
                ErrorClass.TRANSIENT, "provider request timed out"
            ) from error
        except httpx.NetworkError as error:
            raise ProviderError(
                ErrorClass.TRANSIENT, "provider network failure"
            ) from error
        if not 200 <= response.status_code < 300:
            raise _error_from_response(response)
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError(
                ErrorClass.TRANSIENT, "provider returned invalid JSON"
            ) from error
        models = payload.get("data", ())
        result = []
        for model in models:
            model_id = model.get("id") if isinstance(model, dict) else None
            if not model_id:
                continue
            architecture = model.get("architecture") or {}
            output_modalities = architecture.get("output_modalities") or []
            if output_modalities and "text" not in output_modalities:
                continue
            supported = set(model.get("supported_parameters") or ())
            top_provider = model.get("top_provider") or {}
            result.append(
                {
                    "id": str(model_id),
                    "name": str(model_id),
                    "context_window": model.get("context_length"),
                    "output_limit": top_provider.get("max_completion_tokens"),
                    "supports_text": True,
                    "supports_tools": "tools" in supported,
                    "supports_structured": bool(
                        {"response_format", "structured_outputs"} & supported
                    ),
                }
            )
        return result


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
                    responseSchema=_gemini_schema(request.structured_schema),
                )
            if generation:
                payload["generationConfig"] = generation
            declarations = [tool.get("function", tool) for tool in request.tools]
            if declarations:
                payload["tools"] = [{"functionDeclarations": declarations}]
            try:
                raw = await _post_json(
                    self.client,
                    f"{self.base_url}/models/{request.model}:generateContent?key={credential}",
                    payload,
                    {"Content-Type": "application/json"},
                    self.timeout_seconds,
                )
            except ProviderError as error:
                retired_model = (
                    error.status == 404
                    and "model" in str(error).lower()
                    and "no longer available" in str(error).lower()
                )
                if (
                    retired_model
                    or (
                        request.structured_schema is not None
                        and error.error_class is ErrorClass.INPUT
                        and error.status == 400
                    )
                ):
                    raise ProviderError(
                        ErrorClass.CAPABILITY,
                        str(error),
                        retry_after=error.retry_after,
                        status=error.status,
                        error_type=error.error_type,
                    ) from error
                raise
        candidate = raw.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", ())
        text = "".join(
            part.get("text", "") for part in parts if not part.get("thought", False)
        )
        returned_reasoning = "".join(
            part.get("text", "") for part in parts if part.get("thought", False)
        )
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
            returned_reasoning=returned_reasoning or None,
            reasoning_field=(
                "candidates.content.parts[thought]" if returned_reasoning else None
            ),
        )

    async def sync_models(self, credential: str) -> list[dict[str, Any]]:
        if self.client is None:
            return []
        url = (
            f"{self.base_url}/models"
            if not self.base_url.endswith("/models")
            else self.base_url
        )
        try:
            response = await self.client.get(
                url,
                params={"key": credential},
                timeout=self.timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", data.get("data", []))
                result = []
                for m in models:
                    name = m.get("name", "")
                    mid = (
                        name.split("/")[-1]
                        if "/" in name
                        else (m.get("id") or m.get("name"))
                    )
                    if mid:
                        mid = str(mid)
                        lowered = mid.lower()
                        is_text = not any(
                            p in lowered
                            for p in (
                                "embedding",
                                "embed",
                                "tts",
                                "whisper",
                                "audio",
                                "speech",
                                "moderation",
                                "dall-e",
                                "imagen",
                                "image",
                                "stable-diffusion",
                                "flux",
                            )
                        )
                        supports_tools = not any(
                            p in lowered
                            for p in (
                                "embedding",
                                "embed",
                                "tts",
                                "whisper",
                                "audio",
                                "speech",
                                "moderation",
                                "dall-e",
                                "imagen",
                                "image",
                                "stable-diffusion",
                                "flux",
                            )
                        )
                        if is_text:
                            result.append(
                                {
                                    "id": mid,
                                    "name": m.get("displayName", mid),
                                    "context_window": m.get("inputTokenLimit", 128_000),
                                    "output_limit": m.get("outputTokenLimit", 8_192),
                                    "supports_text": is_text,
                                    "supports_tools": supports_tools,
                                    "supports_structured": supports_tools,
                                }
                            )
                return result
        except Exception:
            pass
        return []


class AnthropicAdapter:
    kind = AdapterKind.OPENAI_COMPATIBLE

    def __init__(
        self,
        call: InjectedCall | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.anthropic.com",
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
            system_text = ""
            messages = []
            for msg in request.messages:
                if msg.get("role") == "system":
                    system_text = str(msg.get("content", ""))
                else:
                    messages.append(msg)
            payload: dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "max_tokens": request.max_output_tokens or 4000,
            }
            if system_text:
                payload["system"] = system_text
            raw = await _post_json(
                self.client,
                f"{self.base_url}/v1/messages",
                payload,
                {
                    "x-api-key": credential,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                self.timeout_seconds,
            )
        content_blocks = raw.get("content", [])
        text = "".join(
            b.get("text", "") for b in content_blocks if b.get("type") == "text"
        )
        usage = raw.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        return ModelResponse(
            text=text,
            tool_calls=(),
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            finish_reason=raw.get("stop_reason"),
            response_id=raw.get("id"),
            provider_id="anthropic",
            model_id=raw.get("model"),
        )

    async def sync_models(self, credential: str) -> list[dict[str, Any]]:
        if self.client is None:
            return []
        url = (
            f"{self.base_url}/v1/models"
            if not self.base_url.endswith("/v1")
            else f"{self.base_url}/models"
        )
        try:
            response = await self.client.get(
                url,
                headers={
                    "x-api-key": credential,
                    "anthropic-version": "2023-06-01",
                },
                timeout=self.timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", data.get("models", []))
                result = []
                for m in models:
                    mid = m.get("id") or m.get("name")
                    if mid:
                        mid = str(mid)
                        lowered = mid.lower()
                        is_text = not any(
                            p in lowered
                            for p in (
                                "embedding",
                                "embed",
                                "tts",
                                "whisper",
                                "audio",
                                "speech",
                                "moderation",
                                "dall-e",
                                "imagen",
                                "image",
                                "stable-diffusion",
                                "flux",
                            )
                        )
                        supports_tools = not any(
                            p in lowered
                            for p in (
                                "embedding",
                                "embed",
                                "tts",
                                "whisper",
                                "audio",
                                "speech",
                                "moderation",
                                "dall-e",
                                "imagen",
                                "image",
                                "stable-diffusion",
                                "flux",
                            )
                        )
                        if is_text:
                            result.append(
                                {
                                    "id": mid,
                                    "name": m.get("display_name", m.get("name", mid)),
                                    "context_window": 200_000,
                                    "output_limit": 8_192,
                                    "supports_text": is_text,
                                    "supports_tools": supports_tools,
                                    "supports_structured": False,
                                }
                            )
                return result
        except Exception:
            pass
        return []


class GroqAdapter(OpenAIAdapter):
    kind = AdapterKind.OPENAI_COMPATIBLE

    def __init__(
        self,
        call: InjectedCall | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.groq.com/openai",
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            call, client=client, base_url=base_url, timeout_seconds=timeout_seconds
        )
