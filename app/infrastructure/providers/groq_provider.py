"""Groq AI Provider implementation."""

from __future__ import annotations

import json
import logging
import time

import httpx

from app.domain.ai import (
    AIConnectionError,
    AIError,
    AIProvider,
    AIRateLimitError,
    AITimeoutError,
)
from app.infrastructure.config.settings import GroqSettings, get_groq_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


class GroqProvider(AIProvider):
    """Implementation of AIProvider using the Groq API (OpenAI compatible)."""

    def __init__(
        self,
        settings: GroqSettings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_groq_settings()
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(
            base_url=self.settings.base_url,
            headers={
                "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        if self._owns_client and self.http_client is not None:
            self.http_client.close()

    def __enter__(self) -> GroqProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def generate(self, prompt: str) -> str:
        """Generate a text response using the Groq API."""
        if not self.settings.is_configured:
            raise ValueError("Groq provider is not configured. API key is missing.")

        payload = {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.settings.temperature,
        }
        
        # Determine max_tokens dynamically based on prompt size
        # Estimate prompt tokens (roughly 1 token = 4 chars)
        prompt_tokens = len(prompt) // 4
        max_tokens = getattr(self.settings, "max_tokens", None)
        
        if max_tokens is not None:
            # If the prompt is massive (e.g. during article analysis), 
            # shrink max_tokens to prevent exceeding the Groq free tier limit
            if prompt_tokens > 8000:
                max_tokens = min(max_tokens, 1000)
            payload["max_tokens"] = max_tokens

        logger.info("Starting Groq API request for model %s", self.settings.model)

        attempt = 1
        delay = 1.0

        while True:
            start_time = time.time()
            try:
                response = self.http_client.post("/chat/completions", json=payload)
                latency = time.time() - start_time
                logger.debug("Groq request completed in %.2fs", latency)

                if response.status_code == 429:
                    if attempt < _MAX_RETRIES:
                        logger.warning("Groq rate limit (429). Retrying in %.1fs...", delay)
                        time.sleep(delay)
                        attempt += 1
                        delay *= 2.0
                        continue
                    raise AIRateLimitError("Groq API rate limit exceeded.")

                if response.status_code in (500, 502, 503, 504) and attempt < _MAX_RETRIES:
                    logger.warning(
                        "Groq server error (HTTP %d). Retrying in %.1fs...", 
                        response.status_code, delay
                    )
                    time.sleep(delay)
                    attempt += 1
                    delay *= 2.0
                    continue

                if response.status_code >= 400:
                    try:
                        error_data = response.json()
                        error_msg = json.dumps(error_data)
                    except Exception:
                        error_msg = response.text
                    
                    logger.error("Groq API error (HTTP %d): %s", response.status_code, error_msg)
                    raise AIError(f"Groq API Error: {error_msg}")

                data = response.json()
                if not isinstance(data, dict):
                    raise AIError("Unexpected response format from Groq API (not a JSON object).")

                choices = data.get("choices")
                if not choices or not isinstance(choices, list):
                    raise AIError("No choices returned from Groq API.")

                message = choices[0].get("message")
                if not message or not isinstance(message, dict):
                    raise AIError("Invalid message structure returned from Groq API.")
                    
                content = message.get("content")
                if content is None:
                    raise AIError("Message content is null in Groq API response.")

                return str(content)

            except httpx.HTTPError as exc:
                latency = time.time() - start_time
                is_transient = isinstance(
                    exc,
                    (
                        httpx.TimeoutException,
                        httpx.ConnectError,
                        httpx.ReadError,
                    ),
                )
                
                if is_transient and attempt < _MAX_RETRIES:
                    logger.warning(
                        "Groq network error (%s) after %.2fs. Retrying in %.1fs...", 
                        type(exc).__name__, latency, delay
                    )
                    time.sleep(delay)
                    attempt += 1
                    delay *= 2.0
                    continue
                
                logger.error("Groq request failed: %s", exc)
                if isinstance(exc, httpx.TimeoutException):
                    raise AITimeoutError(f"Groq API request timed out: {exc}") from exc
                elif isinstance(exc, httpx.ConnectError):
                    raise AIConnectionError(f"Could not connect to Groq API: {exc}") from exc
                else:
                    raise AIError(f"Groq API network error: {exc}") from exc
