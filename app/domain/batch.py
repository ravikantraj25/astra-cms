"""Domain models for batch processing."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PostBatchResult(BaseModel):
    """Result of processing a single WordPress post in a batch."""

    post_id: int = Field(description="WordPress post ID.")
    title: str = Field(default="", description="Post title.")
    status: str = Field(
        default="skipped", description="Result status ('success', 'failed', 'skipped')."
    )
    draft_url: str = Field(default="", description="Draft review URL if published successfully.")
    error_message: str = Field(default="", description="Error description if processing failed.")


class BatchSummaryReport(BaseModel):
    """Overall statistics and results for a batch processing run."""

    total_posts: int = Field(default=0, description="Total candidate posts considered.")
    successful: int = Field(
        default=0, description="Number of successfully updated and published posts."
    )
    failed: int = Field(default=0, description="Number of posts that failed processing.")
    skipped: int = Field(
        default=0, description="Number of posts skipped due to filters or errors."
    )
    draft_urls: list[str] = Field(
        default_factory=list, description="List of generated draft URLs."
    )
    results: list[PostBatchResult] = Field(
        default_factory=list, description="Individual post results."
    )
