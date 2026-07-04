"""
Offline, mocked unit tests for core/provider_models.py
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.db.schema import ProviderConfig, ProviderKey
from app.core.provider_models import fetch_live_models


@pytest.fixture
def provider():
    return ProviderConfig(
        id=42,
        name="Test OpenAI Compat",
        provider_type="openai",
        base_url="https://api.openai.com/v1",
    )


class TestFetchLiveModelsMocked:
    @pytest.mark.asyncio
    async def test_openai_compat_parser_success(self, provider):
        """Test parser for standard OpenAI compat JSON format."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        # Mock both _get_api_key and httpx.AsyncClient.get
        with patch("app.core.provider_models._get_api_key", return_value="sk-test-key"), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await fetch_live_models(provider)
            assert models == ["gpt-4", "gpt-3.5-turbo"]
            mock_get.assert_called_once()
            # Check authorization header
            headers = mock_get.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer sk-test-key"

    @pytest.mark.asyncio
    async def test_ollama_parser_success(self):
        """Test parser for Ollama's local tags API format."""
        ollama_provider = ProviderConfig(
            id=43,
            name="My Ollama",
            provider_type="ollama",
            base_url="http://localhost:11434",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3:latest"},
                {"name": "mistral:latest"},
                {"name": "phi3"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.provider_models._get_api_key", return_value=None), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await fetch_live_models(ollama_provider)
            # Should strip ':latest' suffix
            assert models == ["llama3", "mistral", "phi3"]

    @pytest.mark.asyncio
    async def test_anthropic_parser_success(self):
        """Test parser for Anthropic models list format."""
        anthropic_provider = ProviderConfig(
            id=44,
            name="My Anthropic",
            provider_type="anthropic",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "claude-3-opus", "type": "model"},
                {"id": "claude-3-sonnet", "type": "model"},
                {"id": "some-other-thing", "type": "not-model"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.provider_models._get_api_key", return_value="ant-key"), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await fetch_live_models(anthropic_provider)
            assert models == ["claude-3-opus", "claude-3-sonnet"]
            headers = mock_get.call_args[1]["headers"]
            assert headers["x-api-key"] == "ant-key"
            assert headers["anthropic-version"] == "2023-06-01"

    @pytest.mark.asyncio
    async def test_gemini_parser_success(self):
        """Test parser for Gemini models list API."""
        gemini_provider = ProviderConfig(
            id=45,
            name="My Gemini",
            provider_type="gemini",
        )
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "models/gemini-1.5-flash"},
                {"name": "models/gemini-1.5-pro"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.provider_models._get_api_key", return_value="gem-key"), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            models = await fetch_live_models(gemini_provider)
            assert models == ["gemini-1.5-flash", "gemini-1.5-pro"]
            headers = mock_get.call_args[1]["headers"]
            assert headers["x-goog-api-key"] == "gem-key"

    @pytest.mark.asyncio
    async def test_missing_api_key_for_key_required_provider_returns_empty(self, provider):
        with patch("app.core.provider_models._get_api_key", return_value=None), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            models = await fetch_live_models(provider)
            assert models == []
            mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_provider_type_returns_empty(self):
        invalid_provider = ProviderConfig(id=99, name="Bad", provider_type="nonexistent")
        models = await fetch_live_models(invalid_provider)
        assert models == []

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, provider):
        with patch("app.core.provider_models._get_api_key", return_value="key"), \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection timeout")
            models = await fetch_live_models(provider)
            assert models == []
