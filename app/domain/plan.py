"""Domain models for update planning."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    UPDATE = "Update"
    SKIP = "Skip"
    DELETE = "Delete"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SectionDecision(BaseModel):
    """AI-generated decision for an individual section.

    The AI inspects each section's raw HTML and decides whether to
    Update, Skip, or Delete it.  This replaces the old heuristic
    keyword-matching approach with a per-section AI judgment.
    """

    model_config = ConfigDict(extra="forbid")

    astra_id: str | None = Field(default=None, description="Unique data-astra-id of the section.")
    section: str = Field(min_length=1, description="Section name (must match a detected section).")
    action: ActionType = Field(description="Update, Skip, or Delete.")
    reason: str = Field(min_length=1, description="Why the AI chose this action.")
    priority: Priority = Field(description="High, Medium, or Low.")
    confidence: int = Field(ge=0, le=100, description="Confidence score (0-100).")


# Maintain backward compatibility for modules importing UpdateAction
UpdateAction = SectionDecision


class AnalysisResult(BaseModel):
    """The strictly typed analysis output from the AI.

    Now includes ``section_decisions`` — a per-section list of AI
    judgments — alongside the legacy summary fields.
    """

    model_config = ConfigDict(extra="forbid")

    new_title: str | None = Field(
        default=None,
        description="Suggested updated title for the article, if any.",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="List of evergreen strengths.",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="List of outdated elements.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Targeted improvement suggestions.",
    )
    # Kept only for backward compatibility with existing test mocks
    confidence_scores: dict[str, int] = Field(
        default_factory=dict,
        description="Legacy confidence scores per section (optional).",
    )
    section_decisions: list[SectionDecision] = Field(
        default_factory=list,
        description="AI decisions for every parsed section.",
    )


class UpdatePlan(BaseModel):
    """The complete content update plan."""

    new_title: str | None = Field(
        default=None,
        description="Optional new title for the WordPress post.",
    )
    custom_instructions: str | None = Field(
        default=None,
        description="Optional custom instructions injected during analysis.",
    )
    actions: list[UpdateAction] = Field(
        default_factory=list,
        description="List of actions to perform on the article.",
    )


class UpdateReport(BaseModel):
    """Telemetry and reporting for the HTML Update Engine."""

    updated_sections: list[str] = Field(
        default_factory=list, description="Sections successfully updated."
    )
    skipped_sections: list[str] = Field(
        default_factory=list, description="Sections skipped or ignored."
    )
    confidence_score: float = Field(
        default=0.0, description="Average confidence of applied updates."
    )
    section_confidences: dict[str, float] = Field(
        default_factory=dict, description="Confidence score for every updated section."
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings encountered during generation."
    )
    processing_time_seconds: float = Field(
        default=0.0, description="Time taken to run the update engine."
    )
