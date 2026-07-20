"""Domain models for section validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SectionValidationResult(BaseModel):
    """Result of validating a single generated section against strict rules."""

    is_valid: bool = Field(..., description="True if no rules were violated.")
    failed_rules: list[str] = Field(default_factory=list, description="List of specific rule violation messages.")

    def add_failure(self, message: str) -> None:
        """Record a validation failure."""
        self.is_valid = False
        self.failed_rules.append(message)
