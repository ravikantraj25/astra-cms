"""AI provider interfaces and models."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AIError(Exception):
    """Base exception for all AI provider failures."""


class AIRateLimitError(AIError):
    """Raised when the AI provider rate limits the request."""


class AIConnectionError(AIError):
    """Raised when the AI provider cannot be reached."""


class AITimeoutError(AIError):
    """Raised when the AI provider times out."""


class AIResponseError(AIError):
    """Raised when the AI provider returns a malformed or invalid response."""


class AIAuthenticationError(AIError):
    """Raised when authentication with the AI provider fails."""


class AIProvider(ABC):
    """Abstract base class for all AI text generation providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt.

        Args:
            prompt: The text prompt to send to the AI model.

        Returns:
            The generated text response.
        """
        ...
