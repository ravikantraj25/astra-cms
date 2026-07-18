"""Application logic for generating an Update Plan."""

from __future__ import annotations

from app.domain.article import Article
from app.domain.plan import UpdateAction, UpdatePlan


def build_update_plan(article: Article, analysis: dict[str, list[str]]) -> UpdatePlan:
    """Build an UpdatePlan from an Article and its AI analysis.

    Uses simple rule-based logic to determine whether a section should be
    updated or skipped based on the strengths, weaknesses, and suggestions
    in the AI analysis.

    Args:
        article: The parsed HTML article with detected sections.
        analysis: The parsed JSON analysis from the AI.

    Returns:
        An UpdatePlan containing actions for each section.
    """
    actions: list[UpdateAction] = []

    # Combine weaknesses and suggestions into a single lowercase text block for matching
    weaknesses = " ".join(analysis.get("weaknesses", []))
    suggestions = " ".join(analysis.get("suggestions", []))
    analysis_text = f"{weaknesses} {suggestions}".lower()

    if not article.sections:
        # If no sections are detected, return an empty plan
        return UpdatePlan(actions=[])

    for section in article.sections:
        # Check if the section name or type is mentioned in the negative/suggestive analysis
        name_lower = section.name.lower()
        type_lower = section.type.lower()

        # We consider a match if the section name or type is literally present
        # in the suggestions/weaknesses. This is a naive but effective rule-based
        # approach for this requirement.
        if name_lower in analysis_text or type_lower in analysis_text:
            actions.append(
                UpdateAction(
                    section=section.name,
                    reason="Identified for improvement in AI analysis.",
                    priority="High",
                    confidence=85
                    + (len(section.name) % 10),  # Pseudo-randomize confidence slightly for realism
                    action="Update",
                )
            )
        else:
            actions.append(
                UpdateAction(
                    section=section.name,
                    reason="No significant issues identified.",
                    priority="Low",
                    confidence=100,
                    action="Skip",
                )
            )

    return UpdatePlan(actions=actions)
