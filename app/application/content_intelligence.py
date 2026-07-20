"""Application service for Content Intelligence analysis."""

import json
import logging
import re
from pydantic import ValidationError
from bs4 import BeautifulSoup

from app.domain.ai import AIProvider, AIError
from app.domain.article import Article
from app.domain.intelligence import ArticleAnalysis
from app.application.intelligence_prompt import build_intelligence_prompt

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code blocks (e.g., ```json ... ```) from text."""
    clean = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE)
    clean = re.sub(r"```$", "", clean, flags=re.MULTILINE)
    return clean.strip()


class ContentIntelligenceAnalyzer:
    """Analyzes an article to produce structured content intelligence."""

    def __init__(self, ai_provider: AIProvider) -> None:
        """Initialize the analyzer with an AI provider."""
        self.ai_provider = ai_provider

    def analyze(self, article: Article) -> ArticleAnalysis:
        """Analyze the article and return structured intelligence.

        Args:
            article: The parsed Article domain model.

        Returns:
            A populated ArticleAnalysis object.

        Raises:
            AIError: If the AI provider fails to return valid JSON after retries.
        """
        logger.info("Extracting raw text for content intelligence analysis.")
        
        # We strip HTML to reduce token usage and help the AI focus on semantic meaning
        soup = BeautifulSoup(article.raw_html, "html.parser")
        article_text = soup.get_text(separator="\n", strip=True)

        prompt = build_intelligence_prompt(article_text)
        
        for attempt in range(_MAX_RETRIES + 1):
            logger.info("Content Intelligence generation attempt %d/%d", attempt + 1, _MAX_RETRIES + 1)
            try:
                response_text = self.ai_provider.generate(prompt)
                clean_text = _strip_markdown_fences(response_text)
                
                # Try to parse as JSON
                try:
                    data = json.loads(clean_text)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse Content Intelligence output as JSON: %s", e)
                    continue
                
                # Try to validate with Pydantic
                try:
                    intelligence = ArticleAnalysis.model_validate(data)
                    logger.info("Successfully generated Content Intelligence.")
                    return intelligence
                except ValidationError as e:
                    logger.warning("Content Intelligence output failed validation: %s", e)
                    continue

            except AIError as e:
                logger.error("AIProvider error during Content Intelligence generation: %s", e)
                # Re-raise on the last attempt
                if attempt == _MAX_RETRIES:
                    raise e
                continue
                
        raise AIError(f"Failed to generate valid Content Intelligence after {_MAX_RETRIES + 1} attempts.")
