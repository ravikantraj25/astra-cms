"""Tests for HTML generation logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.generator import generate_updated_article
from app.domain.article import Article, Section
from app.domain.plan import UpdateAction, UpdatePlan


def test_generate_updated_article_skips_and_deletes() -> None:
    """Should correctly skip and delete sections without calling AI."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">Sec 1</p><p data-astra-id="2">Sec 2</p>',
        sections=[
            Section(
                name="Section 1",
                type="Paragraph",
                astra_id="1",
                content="<p>Sec 1</p>",
            ),
            Section(
                name="Section 2",
                type="Paragraph",
                astra_id="2",
                content="<p>Sec 2</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Section 1",
                reason="Skip it",
                priority="Low",
                confidence=100,
                action="Skip",
            ),
            UpdateAction(
                section="Section 2",
                reason="Delete it",
                priority="High",
                confidence=100,
                action="Delete",
            ),
        ]
    )

    mock_ai = MagicMock()

    result, report = generate_updated_article(article, plan, mock_ai)

    assert "<p>Sec 1</p>" in result
    assert "Sec 2" not in result
    assert "data-astra-id" not in result  # Cleaned up
    assert report.skipped_sections == ["Section 1"]
    assert report.updated_sections == ["Section 2"]
    assert report.confidence_score == 100.0
    assert report.section_confidences == {"Section 2": 100.0}
    mock_ai.generate.assert_not_called()


def test_generate_updated_article_updates() -> None:
    """Should call AI for Update actions and replace HTML DOM."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">Sec 1</p><p data-astra-id="2">Sec 2</p>',
        sections=[
            Section(
                name="Section 1",
                type="Paragraph",
                astra_id="1",
                content="<p>Sec 1</p>",
            ),
            Section(
                name="Section 2",
                type="Paragraph",
                astra_id="2",
                content="<p>Sec 2</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Section 1",
                reason="Update 1",
                priority="High",
                confidence=90,
                action="Update",
            ),
            UpdateAction(
                section="Section 2",
                reason="Update 2",
                priority="High",
                confidence=95,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    # Mock AI response - we don't care about order for DOM replacement, but we just provide two
    mock_ai.generate.side_effect = [
        "<ASTRA_HTML_START>\n<p>New Sec 1</p>\n<ASTRA_HTML_END>",
        "<ASTRA_HTML_START>\n<p>New Sec 2</p>\n<ASTRA_HTML_END>",
    ]

    result, report = generate_updated_article(article, plan, mock_ai)

    assert "<p>New Sec 1</p>" in result
    assert "<p>New Sec 2</p>" in result
    assert "data-astra-id" not in result # Ensure cleanup
    
    # Check that the report has the updated sections
    assert "Section 1" in report.updated_sections
    assert "Section 2" in report.updated_sections
    
    assert report.confidence_score == 92.5
    assert report.section_confidences == {"Section 1": 90.0, "Section 2": 95.0}
    assert mock_ai.generate.call_count == 2


def test_generate_full_article_update_success() -> None:
    """Should send full article + plan to AI and parse ASTRA markers."""
    from app.application.generator import generate_full_article_update

    original_html = "<h1>Title</h1><p>Old content</p>"
    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Intro",
                reason="Needs SEO",
                priority="High",
                confidence=85,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "<ASTRA_HTML_START>\n"
        "<h1>Title</h1><p>Updated content with SEO</p>\n"
        "<ASTRA_HTML_END>"
    )

    result, report = generate_full_article_update(original_html, plan, mock_ai)

    assert "<h1>Title</h1>" in result
    assert "Updated content with SEO" in result
    assert "Old content" not in result
    assert report.updated_sections == ["Intro"]
    assert report.confidence_score == 85.0
    mock_ai.generate.assert_called_once()


def test_generate_full_article_update_empty_plan() -> None:
    """Should return original HTML when plan has no actions."""
    from app.application.generator import generate_full_article_update

    original_html = "<h1>Title</h1><p>Content</p>"
    plan = UpdatePlan(actions=[])
    mock_ai = MagicMock()

    result, report = generate_full_article_update(original_html, plan, mock_ai)

    assert result == original_html
    assert report.updated_sections == []
    mock_ai.generate.assert_not_called()


def test_generate_full_article_update_raises_on_ai_error() -> None:
    """Should raise RuntimeError when AI provider fails."""
    from app.application.generator import generate_full_article_update

    original_html = "<h1>Title</h1><p>Content</p>"
    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Intro",
                reason="Needs update",
                priority="High",
                confidence=90,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    mock_ai.generate.side_effect = RuntimeError("API timeout")

    with pytest.raises(RuntimeError, match="API timeout"):
        generate_full_article_update(original_html, plan, mock_ai)


def test_generate_full_article_update_raises_on_bad_response() -> None:
    """Should raise RuntimeError when AI response fails validation."""
    from app.application.generator import generate_full_article_update

    original_html = "<h1>Title</h1>"
    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Intro",
                reason="Update SEO",
                priority="High",
                confidence=80,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    # Missing ASTRA markers — should fail validation
    mock_ai.generate.return_value = "<h1>Title</h1><p>Updated</p>"

    with pytest.raises(RuntimeError, match="exactly one"):
        generate_full_article_update(original_html, plan, mock_ai)


def test_generate_full_article_update_skips_tracked() -> None:
    """Should track skipped sections correctly in the report."""
    from app.application.generator import generate_full_article_update

    original_html = "<h1>Title</h1>"
    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Intro",
                reason="Update SEO",
                priority="High",
                confidence=80,
                action="Update",
            ),
            UpdateAction(
                section="FAQ",
                reason="OK as-is",
                priority="Low",
                confidence=95,
                action="Skip",
            ),
        ]
    )

    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "<ASTRA_HTML_START>\n<h1>Title</h1>\n<ASTRA_HTML_END>"
    )

    result, report = generate_full_article_update(original_html, plan, mock_ai)

    assert "Intro" in report.updated_sections
    assert "FAQ" in report.skipped_sections
    assert report.confidence_score == 80.0


def test_generate_updated_article_preserves_structure() -> None:
    """Should preserve attributes of target tag when updating."""
    article = Article(
        title="Test",
        raw_html='<p id="p1" class="date-txt" data-astra-id="1">Old Date</p>',
        sections=[
            Section(
                name="Date",
                type="Paragraph",
                astra_id="1",
                content='<p id="p1" class="date-txt">Old Date</p>',
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Date",
                reason="Update date",
                priority="High",
                confidence=100,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    # AI returns the p tag but misses the class and id
    mock_ai.generate.return_value = "<ASTRA_HTML_START>\n<p>New Date</p>\n<ASTRA_HTML_END>"

    result, report = generate_updated_article(article, plan, mock_ai)

    # The attributes should be rescued
    assert 'class="date-txt"' in result
    assert 'id="p1"' in result
    assert "New Date" in result
    
    # Run QualityValidator to ensure the generated HTML passes structure validation
    from app.application.quality_validator import QualityValidator
    original_html = '<p id="p1" class="date-txt">Old Date</p>'
    val_report = QualityValidator.validate(original_html, result)
    assert val_report.structure_preserved is True
    assert val_report.prompt_leakage is False
    assert val_report.status == "PASS"


def test_generate_updated_article_strips_markdown() -> None:
    """Should strip markdown fences to prevent validation error and leakage."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">Content</p>',
        sections=[
            Section(
                name="Content",
                type="Paragraph",
                astra_id="1",
                content='<p>Content</p>',
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            UpdateAction(
                section="Content",
                reason="Update",
                priority="High",
                confidence=100,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    # AI includes markdown fences inside the markers (prompt leakage pattern)
    mock_ai.generate.return_value = (
        "<ASTRA_HTML_START>\n"
        "```html\n"
        "<p>Updated Content</p>\n"
        "```\n"
        "<ASTRA_HTML_END>"
    )

    result, report = generate_updated_article(article, plan, mock_ai)

    # Should not throw RuntimeError on validation because fences are stripped
    assert "<p>Updated Content</p>" in result
    assert "```html" not in result
    assert "```" not in result
    assert report.updated_sections == ["Content"]

