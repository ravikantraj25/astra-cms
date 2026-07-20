"""Domain models for HTML quality validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QualityReport(BaseModel):
    """Represents the complete result of a quality validation pass."""

    status: str = Field(..., description="'PASS' if ready to publish, 'FAIL' otherwise.")
    html_valid: bool = Field(True, description="True if HTML parses correctly.")
    prompt_leakage: bool = Field(False, description="True if banned AI phrases are detected.")
    dangerous_html: bool = Field(False, description="True if malicious tags/attributes are found.")
    images_preserved: bool = Field(True, description="True if image count is preserved.")
    links_preserved: bool = Field(True, description="True if link count is preserved.")
    tables_preserved: bool = Field(True, description="True if table count is preserved.")
    structure_preserved: bool = Field(True, description="True if headings, css, ids, and gutenberg structure match.")
    
    word_diff: int = Field(0, description="Difference in word count.")
    html_diff_percent: float = Field(0.0, description="Difference in HTML size as a percentage.")
    
    ready_to_publish: bool = Field(False, description="True if all critical checks passed.")
