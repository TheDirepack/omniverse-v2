import pytest
from sqlmodel import Session
from app.db.schema import ProviderConfig, ProviderKey
from app.core.provider_models import fetch_live_models
from app.db.session import engine
from tests.provider_config import PROVIDER_CREDENTIALS

pytestmark = pytest.mark.slow


def _requires_key(ptype: str) -> bool:
    return ptype not in {"ollama", "custom"}


@pytest.mark.parametrize("ptype", sorted(PROVIDER_CREDENTIALS))
@pytest.mark.asyncio
async def test_fetch_live_models(ptype: str):
    creds = PROVIDER_CREDENTIALS[ptype]

    if _requires_key(ptype) and not creds["api_key"]:
        pytest.skip(f"provider '{ptype}' not configured (set api_key in provider_config.py)")

    if not creds["base_url"] and not _requires_key(ptype):
        pytest.skip(f"provider '{ptype}' base_url not set in provider_config.py")

    # Persist provider so fetch_live_models can look up API key by provider.id
    with Session(engine) as session:
        provider = ProviderConfig(
            name=f"test-{ptype}",
            provider_type=ptype,
            base_url=creds["base_url"],
        )
        session.add(provider)
        session.flush()

        if creds["api_key"]:
            key = ProviderKey(provider_id=provider.id, api_key=creds["api_key"], priority=0)
            session.add(key)

        session.commit()
        session.refresh(provider)

    models = await fetch_live_models(provider)

    assert isinstance(models, list), f"expected list, got {type(models)}"
    assert len(models) > 0, f"fetch_live_models returned 0 models for {ptype}"
    for m in models:
        assert isinstance(m, str) and m.strip(), f"empty or non-string model name: {m!r}"
