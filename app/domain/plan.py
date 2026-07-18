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
    """A complete plan for updating an article."""

    actions: list[UpdateAction] = Field(default_factory=list, description="List of actions.")
