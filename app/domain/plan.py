"""Domain models for update planning."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UpdateAction(BaseModel):
    """An action to take on a specific section."""

    section: str = Field(description="The name of the section (e.g., FAQ, History).")
    reason: str = Field(description="The reason for this action.")
    priority: str = Field(description="Priority of the update (High, Medium, Low).")
    confidence: int = Field(description="Confidence percentage (0-100).")
    action: str = Field(description="The action to perform (Update, Skip, Delete).")


class UpdatePlan(BaseModel):
    """The complete content update plan."""

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
