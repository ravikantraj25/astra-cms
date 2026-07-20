"""Application logic for generating an Update Plan.

Architecture:
    1. Use AI ``section_decisions`` as the primary source of truth.
    2. For any section the AI omitted, apply deterministic fallback rules
       based on year mismatches, date keywords, and dynamic content markers.
    3. Score each decision and emit a final ``UpdatePlan``.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from app.domain.article import Article, Section
from app.domain.plan import (
    AnalysisResult,
    SectionDecision,
    UpdateAction,
    UpdatePlan,
    ActionType,
    Priority,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

def _get_current_year() -> int:
    return datetime.now().year


# Match any 4-digit year in the 2000s
_OUTDATED_YEAR_PATTERN = re.compile(
    r"\b(20\d{2})\b"
)

# Keywords that signal dynamic/time-sensitive content.
_DYNAMIC_KEYWORDS: tuple[str, ...] = (
    "today",
    "this year",
    "expected",
    "schedule",
    "registration",
    "tickets",
    "priority",
    "deadline",
    "upcoming",
    "next year",
)

# Score thresholds and weights for deterministic rule scoring.
_WEIGHT_YEAR_MISMATCH: int = 40
_WEIGHT_DATE_FOUND: int = 20
_WEIGHT_DYNAMIC_KEYWORD: int = 20
_UPDATE_THRESHOLD: int = 30


# ── Deterministic scoring ────────────────────────────────────────────────────


def _section_has_outdated_year(section: Section, current_year: int) -> bool:
    """Check whether a section's HTML references a year older than the current one."""
    content_lower = section.content.lower()
    for match in _OUTDATED_YEAR_PATTERN.finditer(content_lower):
        found_year = int(match.group(1))
        if found_year < current_year:
            return True
    return False


def _section_has_date_content(section: Section) -> bool:
    """Check whether a section contains date patterns like 'October 2025'."""
    return bool(re.search(
        r"(january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+20\d{2}",
        section.content,
        re.IGNORECASE,
    ))


def _section_has_dynamic_keywords(section: Section) -> bool:
    """Check whether a section contains dynamic/time-sensitive keywords."""
    content_lower = section.content.lower()
    return any(kw in content_lower for kw in _DYNAMIC_KEYWORDS)


def _score_section(section: Section) -> tuple[ActionType, int, str]:
    """Score a section using deterministic rules.
    
    Returns:
        A tuple of (action, confidence_score, reason_string).
    """
    score = 0
    reasons: list[str] = []
    
    current_year = _get_current_year()

    if _section_has_outdated_year(section, current_year):
        score += _WEIGHT_YEAR_MISMATCH
        reasons.append(f"Contains year references older than {current_year}")

    if _section_has_date_content(section):
        score += _WEIGHT_DATE_FOUND
        reasons.append("Contains date patterns that may be outdated")

    if _section_has_dynamic_keywords(section):
        score += _WEIGHT_DYNAMIC_KEYWORD
        reasons.append("Contains dynamic/time-sensitive keywords")

    if score >= _UPDATE_THRESHOLD:
        return ActionType.UPDATE, min(75, score), "; ".join(reasons)

    # For SKIP, we return a confidence capped at 75, subtracting any minor scores
    skip_confidence = max(0, 75 - score)
    return ActionType.SKIP, skip_confidence, "No outdated content detected"


# ── Main planner ─────────────────────────────────────────────────────────────


def build_update_plan(
    article: Article,
    analysis: AnalysisResult,
    custom_instructions: str | None = None,
) -> UpdatePlan:
    """Build an UpdatePlan from an Article and its AI analysis.

    Strategy:
        1. Build O(1) lookups for AI decisions by astra_id and section name.
        2. Validate AI decisions (clamp confidence, validate enums).
        3. For each detected section:
           a. Prefer AI decision by astra_id, then by name.
           b. Fallback to deterministic scoring if missing.
           c. Apply DELETE validation and downgrade if necessary.
        4. Warn about any AI decisions that referenced unknown sections.
    """
    if not article.sections:
        return UpdatePlan(
            new_title=analysis.new_title,
            custom_instructions=custom_instructions,
        )

    # 1. Build lookups and validate decisions
    decisions_by_astra_id: dict[str, SectionDecision] = {}
    decisions_by_name: dict[str, SectionDecision] = {}

    for d in analysis.section_decisions:
        # Defensive validation without mutation
        try:
            action = ActionType(d.action)
        except ValueError:
            action = ActionType.SKIP
            
        try:
            priority = Priority(d.priority)
        except ValueError:
            priority = Priority.LOW
            
        confidence = min(100, max(0, getattr(d, 'confidence', 0)))
        
        validated_d = SectionDecision(
            astra_id=d.astra_id,
            section=d.section,
            action=action,
            reason=d.reason,
            priority=priority,
            confidence=confidence,
        )

        # Register by astra_id (if provided)
        if getattr(validated_d, "astra_id", None):
            if validated_d.astra_id in decisions_by_astra_id:
                logger.warning("Duplicate AI decision for astra_id: %s", validated_d.astra_id)
                if validated_d.confidence > decisions_by_astra_id[validated_d.astra_id].confidence:
                    decisions_by_astra_id[validated_d.astra_id] = validated_d
            else:
                decisions_by_astra_id[validated_d.astra_id] = validated_d

        # Register by name (always)
        name_key = validated_d.section.lower()
        if name_key in decisions_by_name:
            logger.warning("Duplicate AI decision for section name: %s", validated_d.section)
            if validated_d.confidence > decisions_by_name[name_key].confidence:
                decisions_by_name[name_key] = validated_d
        else:
            decisions_by_name[name_key] = validated_d

    actions: list[UpdateAction] = []
    used_ai_sections = set()

    for section in article.sections:
        # Prefer astra_id match, fallback to name match
        ai_decision = decisions_by_astra_id.get(section.astra_id)
        if not ai_decision:
            ai_decision = decisions_by_name.get(section.name.lower())

        if ai_decision:
            used_ai_sections.add(ai_decision.section)
            action = ai_decision.action
            confidence = ai_decision.confidence
            reason = ai_decision.reason
            priority = ai_decision.priority

            # Validate DELETE actions
            if action == ActionType.DELETE:
                reason_lower = (reason or "").lower()
                is_valid_reason = any(w in reason_lower for w in ["duplicate", "irrelevant", "obsolete", "filler"])
                
                # Accept if confidence >= 90 OR (confidence >= 70 and has valid reason)
                if not (confidence >= 90 or (confidence >= 70 and is_valid_reason)):
                    action = ActionType.SKIP
                    reason = f"Downgraded from Delete to Skip due to low confidence ({confidence}%) and insufficient reason"
                    priority = Priority.LOW
                    logger.warning(
                        "Invalid DELETE downgrade for section: %s (reason: %s)",
                        section.name,
                        ai_decision.reason,
                    )
        else:
            action, confidence, reason = _score_section(section)
            priority = Priority.HIGH if action == ActionType.UPDATE else Priority.LOW

        actions.append(
            UpdateAction(
                astra_id=section.astra_id,
                section=section.name,
                reason=reason,
                priority=priority,
                confidence=confidence,
                action=action,
            )
        )

    # Detect unused AI decisions
    for d in analysis.section_decisions:
        if d.section not in used_ai_sections:
            logger.warning("Unknown AI section: %s", d.section)

    return UpdatePlan(
        new_title=analysis.new_title,
        custom_instructions=custom_instructions,
        actions=actions,
    )
