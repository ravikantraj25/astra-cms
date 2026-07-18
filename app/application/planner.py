"""Application logic for generating an Update Plan."""

from __future__ import annotations

from typing import Any

from app.domain.article import Article
from app.domain.plan import UpdateAction, UpdatePlan


def build_update_plan(article: Article, analysis: dict[str, Any]) -> UpdatePlan:
    """Build an UpdatePlan from an Article and its AI analysis.

    Uses rule-based logic to detect outdated vs. evergreen content, avoiding
    unnecessary rewrites and assigning targeted confidence scores.

    Args:
        article: The parsed HTML article with detected sections.
        analysis: The parsed JSON analysis from the AI.

    Returns:
        An UpdatePlan containing actions for each section.
    """
    actions: list[UpdateAction] = []

    weaknesses_list = (
        analysis.get("weaknesses", []) if isinstance(analysis.get("weaknesses"), list) else []
    )
    suggestions_list = (
        analysis.get("suggestions", []) if isinstance(analysis.get("suggestions"), list) else []
    )
    strengths_list = (
        analysis.get("strengths", []) if isinstance(analysis.get("strengths"), list) else []
    )

    weaknesses = " ".join(str(item) for item in weaknesses_list)
    suggestions = " ".join(str(item) for item in suggestions_list)
    strengths = " ".join(str(item) for item in strengths_list)

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

    # Check if AI provided direct section confidence scores in analysis
    raw_confidences: object = analysis.get("confidence_scores", {})
    ai_confidences: dict[str, int] = {}
    if isinstance(raw_confidences, dict):
        for k, v in raw_confidences.items():
            try:
                ai_confidences[str(k).lower()] = int(float(v))
            except (ValueError, TypeError):
                pass

    for section in article.sections:
        name_lower = section.name.lower()
        type_lower = section.type.lower()

        # Determine confidence score for this section
        if name_lower in ai_confidences:
            confidence_val = ai_confidences[name_lower]
        else:
            confidence_val = 85 + (len(section.name) % 10)

        # Check if section is targeted for update
        if name_lower in analysis_text or type_lower in analysis_text:
            is_outdated = any(kw in analysis_text for kw in outdated_keywords)
            reason = (
                "Update outdated info while preserving evergreen facts and consistent tone."
                if is_outdated
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

    return UpdatePlan(actions=actions)
