"""Groq AI Provider implementation."""

from __future__ import annotations

import httpx

from app.domain.ai import AIProvider
from app.infrastructure.config.settings import GroqSettings, get_groq_settings


class GroqProvider(AIProvider):
    """Implementation of AIProvider using the Groq API (OpenAI compatible)."""

    def __init__(
        self,
        settings: GroqSettings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_groq_settings()
        self.http_client = http_client or httpx.Client(
            base_url=self.settings.base_url,
            headers={
                "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def generate(self, prompt: str) -> str:
        """Generate a text response using the Groq API."""
        if not self.settings.is_configured:
            raise ValueError("Groq provider is not configured. API key is missing.")

        response = self.http_client.post(
            "/chat/completions",
            json={
                "model": self.settings.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
        )

        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No choices returned from Groq API.")

        message = choices[0].get("message", {})
        return str(message.get("content", ""))
