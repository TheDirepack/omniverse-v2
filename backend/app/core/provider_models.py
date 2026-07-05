import logging
import httpx
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import ProviderConfig, ProviderKey

logger = logging.getLogger(__name__)

PROVIDER_ENDPOINTS = {
    "ollama": lambda base: f"{base.rstrip('/')}/api/tags",
    "custom": lambda base: f"{base.rstrip('/')}/models" if base.rstrip('/').endswith('/v1') else f"{base.rstrip('/')}/v1/models",
    "openai": lambda _: "https://api.openai.com/v1/models",
    "anthropic": lambda _: "https://api.anthropic.com/v1/models",
    "gemini": lambda _: "https://generativelanguage.googleapis.com/v1/models",
    "groq": lambda _: "https://api.groq.com/openai/v1/models",
    "openrouter": lambda _: "https://openrouter.ai/api/v1/models",
}

NO_KEY_TYPES = {"ollama", "custom"}


def _get_api_key(provider_id: int) -> str | None:
    with Session(engine) as session:
        key = session.exec(
            select(ProviderKey).where(ProviderKey.provider_id == provider_id).order_by(ProviderKey.priority)
        ).first()
        return key.api_key if key else None


def _parse_ollama(data: dict) -> list[str]:
    return [m["name"].removesuffix(":latest") for m in data.get("models", [])]


def _parse_openai_compat(data: dict) -> list[str]:
    return [m["id"] for m in data.get("data", [])]


def _parse_anthropic(data: dict) -> list[str]:
    return [m["id"] for m in data.get("data", []) if m["type"] == "model"]


def _parse_gemini(data: dict) -> list[str]:
    return [m["name"].split("/")[-1] for m in data.get("models", [])]


PARSERS = {
    "ollama": _parse_ollama,
    "custom": _parse_openai_compat,
    "openai": _parse_openai_compat,
    "groq": _parse_openai_compat,
    "openrouter": _parse_openai_compat,
    "anthropic": _parse_anthropic,
    "gemini": _parse_gemini,
}


async def fetch_live_models(provider: ProviderConfig) -> list[str]:
    ptype = provider.provider_type
    if ptype not in PROVIDER_ENDPOINTS:
        return []

    url = PROVIDER_ENDPOINTS[ptype](provider.base_url or "")
    headers = {"User-Agent": "OmniverseV2/1.0"}
    api_key = _get_api_key(provider.id)

    if ptype not in NO_KEY_TYPES and not api_key:
        return []

    if ptype in NO_KEY_TYPES:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    elif ptype == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif ptype == "gemini":
        headers["x-goog-api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.exception(f"Failed to fetch models for {ptype} at {url}: {e}")
        return []

    parser = PARSERS.get(ptype)
    if not parser:
        return []

    return parser(data)
