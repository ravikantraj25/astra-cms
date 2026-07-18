"""AI provider interfaces and models."""

from __future__ import annotations

import abc


class AIProvider(abc.ABC):
    """Abstract base class for all AI text generation providers."""

    @abc.abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt.

        Args:
            prompt: The text prompt to send to the AI model.

        Returns:
            The generated text response.
        """
        ...
