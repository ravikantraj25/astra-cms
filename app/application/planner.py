"""Application logic for generating an Update Plan."""

from __future__ import annotations

from typing import Any

from app.domain.article import Article
from app.domain.plan import AnalysisResult, UpdateAction, UpdatePlan


def build_update_plan(article: Article, analysis: AnalysisResult, custom_instructions: str | None = None) -> UpdatePlan:
    """Build an UpdatePlan from an Article and its AI analysis.

    Uses rule-based logic to detect outdated vs. evergreen content, avoiding
    unnecessary rewrites and assigning targeted confidence scores.

    Args:
        article: The parsed HTML article with detected sections.
        analysis: The strictly parsed AnalysisResult from the AI.
        custom_instructions: Optional instructions injected during analysis.

    Returns:
        An UpdatePlan containing actions for each section.
    """
    actions: list[UpdateAction] = []

    weaknesses = " ".join(analysis.weaknesses)
    suggestions = " ".join(analysis.suggestions)
    strengths = " ".join(analysis.strengths)

    analysis_text = f"{weaknesses} {suggestions}".lower()
    strengths_text = strengths.lower()

    outdated_keywords = (
        "outdated",
        "old",
        "expired",
        "year",
        "deprecated",
        "obsolete",
        "broken",
        "past",
    )

    if not article.sections:
        return UpdatePlan(actions=[])

    ai_confidences = {k.lower(): v for k, v in analysis.confidence_scores.items()}

    for section in article.sections:
        name_lower = section.name.lower()
        type_lower = section.type.lower()

        # Determine confidence score for this section
        if name_lower in ai_confidences:
            confidence_val = ai_confidences[name_lower]
        else:
            confidence_val = 85 + (len(section.name) % 10)

        # Check if section is targeted for update
        if custom_instructions or name_lower in analysis_text or type_lower in analysis_text:
            is_outdated = bool(custom_instructions) or any(kw in analysis_text for kw in outdated_keywords)
            reason = (
                f"Apply custom instructions: {custom_instructions}" if custom_instructions
                else "Update outdated info while preserving evergreen facts and consistent tone." if is_outdated
                else "Targeted improvement identified in AI analysis; avoiding unnecessary edits."
            )
            actions.append(
                UpdateAction(
                    section=section.name,
                    reason=reason,
                    priority="High",
                    confidence=min(100, max(0, confidence_val)),
                    action="Update",
                )
            )
        elif name_lower in strengths_text or any(
            kw in strengths_text for kw in ("evergreen", "accurate", "preserve")
        ):
            actions.append(
                UpdateAction(
                    section=section.name,
                    reason="Section contains accurate/evergreen content; preserving unchanged.",
                    priority="Low",
                    confidence=100,
                    action="Skip",
                )
            )
        else:
            actions.append(
                UpdateAction(
                    section=section.name,
                    reason="No significant issues identified; keeping content unchanged.",
                    priority="Low",
                    confidence=100,
                    action="Skip",
                )
            )

    return UpdatePlan(
        new_title=analysis.new_title,
        custom_instructions=custom_instructions,
        actions=actions
    )
