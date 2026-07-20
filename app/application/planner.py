"""Application logic for generating an Update Plan.

Architecture:
    1. Consume Content Intelligence rules.
    2. Prompt the AI to evaluate each section strictly against those rules.
    3. Return a highly prescriptive UpdatePlan for the generator.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from app.domain.ai import AIProvider, AIError
from app.domain.article import Article
from app.domain.intelligence import ArticleAnalysis
from app.domain.plan import UpdatePlan
from app.application.prompt_builder import build_planner_prompt

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code blocks (e.g., ```json ... ```) from text."""
    clean = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE)
    clean = re.sub(r"```$", "", clean, flags=re.MULTILINE)
    return clean.strip()


class Planner:
    """Generates an UpdatePlan using Content Intelligence."""

    def __init__(self, ai_provider: AIProvider) -> None:
        """Initialize the planner with an AI provider."""
        self.ai_provider = ai_provider

    def build_plan(
        self,
        article: Article,
        intelligence: ArticleAnalysis,
        custom_instructions: str | None = None,
    ) -> UpdatePlan:
        """Build an UpdatePlan from an Article and its Intelligence.

        Args:
            article: The parsed Article domain model.
            intelligence: The intelligence object containing rules.
            custom_instructions: Optional user-supplied instructions.

        Returns:
            A populated UpdatePlan object.

        Raises:
            AIError: If the AI provider fails to return a valid Plan after retries.
        """
        if not article.sections:
            logger.info("No sections detected, generating empty plan.")
            return UpdatePlan(
                new_title=None,
                custom_instructions=custom_instructions,
                actions=[],
            )

        prompt = build_planner_prompt(article, intelligence, custom_instructions)
        
        for attempt in range(_MAX_RETRIES + 1):
            logger.info("Planner generation attempt %d/%d", attempt + 1, _MAX_RETRIES + 1)
            try:
                response_text = self.ai_provider.generate(prompt)
                clean_text = _strip_markdown_fences(response_text)
                
                # Try to parse as JSON
                try:
                    data = json.loads(clean_text)
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse Planner output as JSON: %s", e)
                    continue
                
                # Try to validate with Pydantic
                try:
                    # Enforce that custom_instructions are carried over
                    if custom_instructions and "custom_instructions" not in data:
                        data["custom_instructions"] = custom_instructions
                        
                    plan = UpdatePlan.model_validate(data)
                    
                    # Log warnings for sections that were omitted by the AI
                    planned_sections = {a.section.lower() for a in plan.actions}
                    for section in article.sections:
                        if section.name.lower() not in planned_sections:
                            logger.warning(
                                "AI Planner omitted section: '%s'. It will not be modified.", 
                                section.name
                            )

                    logger.info("Successfully generated UpdatePlan.")
                    return plan
                except ValidationError as e:
                    logger.warning("Planner output failed validation: %s", e)
                    continue

            except AIError as e:
                logger.error("AIProvider error during Planner generation: %s", e)
                # Re-raise on the last attempt
                if attempt == _MAX_RETRIES:
                    raise e
                continue
                
        raise AIError(f"Failed to generate valid Update Plan after {_MAX_RETRIES + 1} attempts.")
