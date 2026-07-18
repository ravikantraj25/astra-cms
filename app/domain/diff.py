"""Domain models for HTML diff comparison.

Provides structures to represent the differences between the original
HTML and the AI-generated HTML updates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiffAction(BaseModel):
    """Represents a specific change identified between two HTML articles."""

    type: str = Field(
        ..., description="The type of change (e.g., 'Added', 'Removed', 'Modified')."
    )
    content: str = Field(..., description="A snippet or identifier of the content that changed.")
    confidence: float = Field(
        default=100.0, description="Confidence score for this diff action (0 to 100)."
    )
    reason: str = Field(default="", description="Reasoning or description for the change.")


class DiffReport(BaseModel):
    """A comprehensive report of all changes between original and updated HTML."""

    added: list[DiffAction] = Field(
        default_factory=list, description="List of elements added in the updated HTML."
    )
    removed: list[DiffAction] = Field(
        default_factory=list, description="List of elements removed from the original HTML."
    )
    modified: list[DiffAction] = Field(
        default_factory=list, description="List of elements modified in the updated HTML."
    )
