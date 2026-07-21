"""Unit tests for the Workflow Engine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.application.workflow import run_analysis_workflow
from app.domain.ai import AITimeoutError, AIError
from app.domain.intelligence import ArticleAnalysis, ArticleType, ContentFreshness, UpdateStrategy, EditingPolicy, PolicyAction
from app.infrastructure.wordpress.exceptions import WordPressError
from app.infrastructure.wordpress.models import WPPost, WPPostDetail


@pytest.fixture
def dummy_intelligence():
    return ArticleAnalysis(
        strategy=UpdateStrategy.SELECTIVE,
        freshness=ContentFreshness.RECURRING_EVENT,
        editing_policy=EditingPolicy(
            article_type=ArticleType.ANNUAL_EVENT,
            year_policy=PolicyAction.UPDATE,
            date_policy=PolicyAction.UPDATE,
            history_policy=PolicyAction.KEEP,
            title_policy=PolicyAction.UPDATE,
            image_policy=PolicyAction.KEEP,
            schema_policy=PolicyAction.KEEP,
            faq_policy=PolicyAction.UPDATE,
            schedule_policy=PolicyAction.UPDATE,
            pricing_policy=PolicyAction.UPDATE,
            metadata_policy=PolicyAction.UPDATE,
            link_policy=PolicyAction.KEEP,
            location_policy=PolicyAction.KEEP,
            seo_policy=PolicyAction.UPDATE
        ),
        required_updates=[],
        forbidden_updates=[],
        temporal_entities=[],
        historical_facts=[],
        event_info=[],
        structural_analysis=[],
        risks=[],
    )


def get_valid_planner_response() -> str:
    """Helper to return valid JSON for Planner."""
    ai_response = {
        "new_title": "Test Title 2025",
        "actions": [
            {
                "section_id": "1",
                "section": "Dates",
                "action": "Update",
                "reason": "Needs new year.",
                "confidence": 0.95,
                "fields_to_update": ["2024 to 2025"],
                "fields_to_preserve": [],
                "forbidden_changes": [],
                "required_entities": [],
                "expected_output": ""
            }
        ]
    }
    return f"```json\n{json.dumps(ai_response)}\n```"


@pytest.fixture
def mock_wp_client() -> MagicMock:
    """Mock WordPress client."""
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=None)

    mock_post = WPPost(
        id=123,
        status="publish",
        author=1,
        title="Test Title",
        content_html="<h2>Conclusion</h2><p>Test paragraph content.</p>",
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
    # Planner only needs one generate call if Intelligence is mocked
    provider.generate.return_value = get_valid_planner_response()
    return provider


@patch("app.application.workflow.ContentIntelligenceAnalyzer")
def test_run_analysis_workflow_success(
    mock_analyzer_cls: MagicMock,
    mock_wp_client: MagicMock, 
    mock_ai_provider: MagicMock, 
    tmp_path: Path,
    dummy_intelligence: ArticleAnalysis
) -> None:
    """Test successful execution of the workflow."""
    post_id = 123
    
    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.analyze.return_value = dummy_intelligence
    mock_analyzer_cls.return_value = mock_analyzer_instance

    artifacts = run_analysis_workflow(
        post_id=post_id,
        wp_client=mock_wp_client,
        ai_provider=mock_ai_provider,
        output_dir=tmp_path,
    )

    mock_wp_client.get_post.assert_called_once_with(post_id)
    assert mock_ai_provider.generate.call_count == 1

    assert "html" in artifacts
    assert "article" in artifacts
    assert "intelligence" in artifacts
    assert "plan" in artifacts

    html_content = artifacts["html"].read_text(encoding="utf-8")
    assert "<p>Test paragraph content.</p>" in html_content

    article_data = json.loads(artifacts["article"].read_text(encoding="utf-8"))
    assert article_data["paragraphs"] == ["Test paragraph content."]

    intel_data = json.loads(artifacts["intelligence"].read_text(encoding="utf-8"))
    assert intel_data["strategy"] == "Selective"

    plan_data = json.loads(artifacts["plan"].read_text(encoding="utf-8"))
    assert "actions" in plan_data


def test_run_analysis_workflow_ai_timeout(
    mock_wp_client: MagicMock, mock_ai_provider: MagicMock, tmp_path: Path
) -> None:
    """Test workflow raises AITimeoutError when AI times out."""
    mock_ai_provider.generate.side_effect = AITimeoutError("AI took too long")

    with pytest.raises(AITimeoutError, match="AI took too long"):
        run_analysis_workflow(
            post_id=123,
            wp_client=mock_wp_client,
            ai_provider=mock_ai_provider,
            output_dir=tmp_path,
        )


def test_run_analysis_workflow_wp_failure(
    mock_wp_client: MagicMock, mock_ai_provider: MagicMock, tmp_path: Path
) -> None:
    """Test workflow raises exception when WordPress fetch fails."""
    mock_wp_client.get_post.side_effect = WordPressError("WP fetch failed")

    with pytest.raises(WordPressError, match="WP fetch failed"):
        run_analysis_workflow(
            post_id=123,
            wp_client=mock_wp_client,
            ai_provider=mock_ai_provider,
            output_dir=tmp_path,
        )
    mock_ai_provider.generate.assert_not_called()


def test_run_analysis_workflow_invalid_json_exhausts_retries(
    mock_wp_client: MagicMock, mock_ai_provider: MagicMock, tmp_path: Path
) -> None:
    """Test workflow raises AIError when intelligence retries fail."""
    mock_ai_provider.generate.side_effect = ["This is definitely not json"] * 4

    with pytest.raises(AIError, match="Failed to generate valid output in ArticleClassifier"):
        run_analysis_workflow(
            post_id=123,
            wp_client=mock_wp_client,
            ai_provider=mock_ai_provider,
            output_dir=tmp_path,
        )
        
    assert mock_ai_provider.generate.call_count == 4
