"""Unit tests for the Workflow Engine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.workflow import run_analysis_workflow
from app.infrastructure.wordpress.models import WPPost, WPPostDetail


@pytest.fixture
def mock_wp_client() -> MagicMock:
    """Mock WordPress client."""
    client = MagicMock()
    # The context manager methods (__enter__ and __exit__) need to be mockable
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=None)

    mock_post = WPPost(
        id=123,
        status="publish",
        author=1,
        title="<h2>Test Title</h2>",
        content_html="<p>Test paragraph content.</p>",
    )
    detail = WPPostDetail(
        post=mock_post, author_name="Admin", categories=[], tags=[], word_count=3
    )
    client.get_post.return_value = detail
    return client


@pytest.fixture
def mock_ai_provider() -> MagicMock:
    """Mock AI Provider."""
    provider = MagicMock()
    # Mocking the AI response with a valid JSON that planner will parse
    ai_response = {
        "weaknesses": ["Test paragraph"],
        "suggestions": ["Improve this"],
        "seo_score": 85,
    }
    provider.generate.return_value = f"```json\n{json.dumps(ai_response)}\n```"
    return provider


def test_run_analysis_workflow_success(
    mock_wp_client: MagicMock, mock_ai_provider: MagicMock, tmp_path: Path
) -> None:
    """Test successful execution of the workflow."""
    post_id = 123

    artifacts = run_analysis_workflow(
        post_id=post_id,
        wp_client=mock_wp_client,
        ai_provider=mock_ai_provider,
        output_dir=tmp_path,
    )

    # Check that client and provider were called
    mock_wp_client.get_post.assert_called_once_with(post_id)
    mock_ai_provider.generate.assert_called_once()

    # Check that the files were created in the output directory
    assert "html" in artifacts
    assert "article" in artifacts
    assert "prompt" in artifacts
    assert "analysis" in artifacts
    assert "plan" in artifacts

    assert (tmp_path / f"post_{post_id}.html").exists()
    assert (tmp_path / "article.json").exists()
    assert (tmp_path / "prompt.txt").exists()
    assert (tmp_path / "analysis.json").exists()
    assert (tmp_path / "update_plan.json").exists()

    # Verify plan contents briefly
    plan_data = json.loads(artifacts["plan"].read_text(encoding="utf-8"))
    assert "actions" in plan_data


def test_run_analysis_workflow_invalid_json(
    mock_wp_client: MagicMock, mock_ai_provider: MagicMock, tmp_path: Path
) -> None:
    """Test workflow handles invalid JSON gracefully."""
    mock_ai_provider.generate.return_value = "This is not json"

    artifacts = run_analysis_workflow(
        post_id=123,
        wp_client=mock_wp_client,
        ai_provider=mock_ai_provider,
        output_dir=tmp_path,
    )

    assert (tmp_path / "analysis.json").exists()
    analysis_data = json.loads(artifacts["analysis"].read_text(encoding="utf-8"))

    # It should fallback to a dictionary with a raw_output key
    assert analysis_data["raw_output"] == "This is not json"
