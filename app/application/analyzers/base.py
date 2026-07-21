"""Base analyzer logic."""

import json
import logging
import re
from typing import TypeVar, Type, Generic

from pydantic import BaseModel, ValidationError

from app.domain.ai import AIProvider, AIError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_MAX_RETRIES = 3


def strip_markdown_fences(text: str) -> str:
    """Remove markdown code blocks (e.g., ```json ... ```) from text."""
    clean = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE)
    clean = re.sub(r"```$", "", clean, flags=re.MULTILINE)
    return clean.strip()


class BaseAnalyzer(Generic[T]):
    """Base class for all specialized analyzers."""
    
    def __init__(self, ai_provider: AIProvider):
        self.ai_provider = ai_provider

    def _generate_and_parse(self, prompt: str, model_cls: Type[T]) -> T:
        """Helper to invoke AI and parse response into the expected Pydantic model."""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response_text = self.ai_provider.generate(prompt)
                clean_text = strip_markdown_fences(response_text)
                
                try:
                    data = json.loads(clean_text)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse output as JSON in %s: %s", self.__class__.__name__, e)
                    continue
                
                try:
                    return model_cls.model_validate(data)
                except ValidationError as e:
                    logger.warning("Output failed validation in %s: %s", self.__class__.__name__, e)
                    continue

            except AIError as e:
                logger.error("AIProvider error in %s: %s", self.__class__.__name__, e)
                if attempt == _MAX_RETRIES:
                    raise e
                continue
                
        raise AIError(f"Failed to generate valid output in {self.__class__.__name__} after {_MAX_RETRIES + 1} attempts.")
