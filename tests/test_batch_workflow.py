"""Tests for the batch processing workflow engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.application.batch_workflow import run_batch_workflow
from app.domain.plan import UpdateReport
from app.infrastructure.wordpress.models import WPPost, WPPostDetail, WPPostList


def test_batch_workflow_success_and_resilience(tmp_path: Path) -> None:
    """Should process multiple posts and continue if one post fails."""
    mock_wp = MagicMock()
    mock_wp.__enter__.return_value = mock_wp
    mock_ai = MagicMock()

    post1 = WPPost(id=1, title="Post 1", content_html="<p>P1</p>")
    post2 = WPPost(id=2, title="Post 2", content_html="<p>P2</p>")
    mock_wp.get_posts.side_effect = [
        WPPostList(posts=[post1, post2], total=2, total_pages=1),
    ]

    # Post 1 succeeds, Post 2 throws an error during analysis
    with (
        patch("app.application.batch_workflow.run_analysis_workflow") as mock_analyze,
        patch("app.application.batch_workflow.generate_updated_article") as mock_gen,
    ):
        plan_file = tmp_path / "plan.json"
        plan_file.write_text('{"actions": []}', encoding="utf-8")
        html_file = tmp_path / "html.html"
        html_file.write_text("<p>P1</p>", encoding="utf-8")

        mock_analyze.side_effect = [
            {"html": html_file, "plan": plan_file},
            RuntimeError("AI Timeout on Post 2"),
        ]
        mock_gen.return_value = ("<p>Updated P1</p>", UpdateReport())
        mock_wp.update_post.return_value = WPPost(id=1, link="https://example.com/draft1")

        report = run_batch_workflow(
            wp_client=mock_wp,
            ai_provider=mock_ai,
            output_dir=tmp_path,
            limit=10,
        )

    assert report.total_posts == 2
    assert report.successful == 1
    assert report.failed == 1
    assert report.skipped == 0
    assert report.draft_urls == ["https://example.com/draft1"]
    assert len(report.results) == 2
    assert report.results[0].status == "success"
    assert report.results[1].status == "failed"
    assert "AI Timeout on Post 2" in report.results[1].error_message


def test_batch_workflow_taxonomy_filtering_and_dry_run(tmp_path: Path) -> None:
    """Should filter posts by category/tag and skip publishing when dry_run=True."""
    mock_wp = MagicMock()
    mock_wp.__enter__.return_value = mock_wp
    mock_ai = MagicMock()

    post1 = WPPost(id=10, title="Tech Post")
    post2 = WPPost(id=20, title="Food Post")
    mock_wp.get_posts.side_effect = [
        WPPostList(posts=[post1, post2], total=2, total_pages=1),
    ]

    mock_wp.get_post.side_effect = [
        WPPostDetail(post=post1, categories=["Technology"], tags=["AI"]),
        WPPostDetail(post=post2, categories=["Cooking"], tags=["Recipes"]),
    ]

    with (
        patch("app.application.batch_workflow.run_analysis_workflow") as mock_analyze,
        patch("app.application.batch_workflow.generate_updated_article") as mock_gen,
    ):
        plan_file = tmp_path / "plan.json"
        plan_file.write_text('{"actions": []}', encoding="utf-8")
        html_file = tmp_path / "html.html"
        html_file.write_text("<p>P1</p>", encoding="utf-8")

        mock_analyze.return_value = {"html": html_file, "plan": plan_file}
        mock_gen.return_value = ("<p>Updated Tech</p>", UpdateReport())

        report = run_batch_workflow(
            wp_client=mock_wp,
            ai_provider=mock_ai,
            output_dir=tmp_path,
            category_filter="Technology",
            dry_run=True,
        )

    assert report.total_posts == 2  # 1 processed + 1 skipped
    assert report.successful == 1
    assert report.skipped == 1
    assert report.failed == 0
    assert report.results[0].status == "skipped"
    assert "Category mismatch" in report.results[0].error_message
    assert report.results[1].status == "success"
    assert report.results[1].draft_url == "N/A (dry-run)"
    mock_wp.update_post.assert_not_called()
