"""Tests for the AI provider."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import SecretStr

from app.infrastructure.config.settings import GroqSettings
from app.infrastructure.providers.groq_provider import GroqProvider


def test_groq_provider_missing_api_key() -> None:
    """It should raise ValueError if API key is not configured."""
    settings = GroqSettings(api_key=SecretStr(""))
    provider = GroqProvider(settings=settings)

    with pytest.raises(ValueError, match="Groq provider is not configured"):
        provider.generate("Hello")


def test_groq_provider_generate_success() -> None:
    """It should return the generated text on success."""
    settings = GroqSettings(api_key=SecretStr("test_key"))
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}
    mock_client.post.return_value = mock_response

    provider = GroqProvider(settings=settings, http_client=mock_client)
    result = provider.generate("Test prompt")

    assert result == "Test response"
    mock_client.post.assert_called_once_with(
        "/chat/completions",
        json={
            "model": settings.model,
            "messages": [{"role": "user", "content": "Test prompt"}],
            "temperature": 0.7,
            "max_tokens": 3000,
        },
    )


def test_groq_provider_generate_no_choices() -> None:
    """It should raise RuntimeError if API returns no choices."""
    settings = GroqSettings(api_key=SecretStr("test_key"))
    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": []}
    mock_client.post.return_value = mock_response

    provider = GroqProvider(settings=settings, http_client=mock_client)

    from app.domain.ai import AIError
    with pytest.raises(AIError, match=r"No choices returned from Groq API\."):
        provider.generate("Test prompt")
