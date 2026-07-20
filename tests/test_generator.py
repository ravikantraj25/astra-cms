"""Tests for HTML generation logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.generator import generate_updated_article
from app.domain.article import Article, Section
from app.domain.plan import SectionDecision, UpdatePlan, ActionType


def test_generate_updated_article_skips_and_deletes() -> None:
    """Should correctly skip and delete sections without calling AI."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">Sec 1</p><p data-astra-id="2">Sec 2</p>',
        sections=[
            Section(
                name="Section 1",
                type="paragraph",
                astra_id="1",
                content="<p>Sec 1</p>",
            ),
            Section(
                name="Section 2",
                type="paragraph",
                astra_id="2",
                content="<p>Sec 2</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Section 1",
                reason="Skip it",
                confidence=1.0,
                action=ActionType.SKIP,
            ),
            SectionDecision(
                section_id="2",
                section="Section 2",
                reason="Delete it",
                confidence=1.0,
                action=ActionType.DELETE,
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
    assert report.confidence_score == 1.0
    assert report.section_confidences == {"Section 2": 1.0}
    mock_ai.generate.assert_not_called()


def test_generate_updated_article_updates() -> None:
    """Should call AI for Update actions and replace HTML DOM."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">Sec 1</p><p data-astra-id="2">Sec 2</p>',
        sections=[
            Section(
                name="Section 1",
                type="paragraph",
                astra_id="1",
                content="<p>Sec 1</p>",
            ),
            Section(
                name="Section 2",
                type="paragraph",
                astra_id="2",
                content="<p>Sec 2</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Section 1",
                reason="Update 1",
                confidence=0.90,
                action=ActionType.UPDATE,
            ),
            SectionDecision(
                section_id="2",
                section="Section 2",
                reason="Update 2",
                confidence=0.95,
                action=ActionType.UPDATE,
            ),
        ]
    )

    mock_ai = MagicMock()
    mock_ai.generate.side_effect = [
        "<ASTRA_HTML_START>\n<p>New Sec 1</p>\n<ASTRA_HTML_END>",
        "<ASTRA_HTML_START>\n<p>New Sec 2</p>\n<ASTRA_HTML_END>",
    ]

    result, report = generate_updated_article(article, plan, mock_ai)

    assert "<p>New Sec 1</p>" in result
    assert "<p>New Sec 2</p>" in result
    assert "data-astra-id" not in result
    
    assert "Section 1" in report.updated_sections
    assert "Section 2" in report.updated_sections
    
    assert report.confidence_score in [0.92, 0.93]
    assert report.section_confidences == {"Section 1": 0.90, "Section 2": 0.95}
    assert mock_ai.generate.call_count == 2


def test_generate_updated_article_low_confidence_abort() -> None:
    """Should skip updating if planner confidence is below 0.70 and record diagnostic."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">Sec 1</p>',
        sections=[
            Section(
                name="Section 1",
                type="paragraph",
                astra_id="1",
                content="<p>Sec 1</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Section 1",
                reason="Not sure",
                confidence=0.50,  # Below 0.70 threshold
                action=ActionType.UPDATE,
            ),
        ]
    )

    mock_ai = MagicMock()
    result, report = generate_updated_article(article, plan, mock_ai)

    # HTML should remain unchanged
    assert "<p>Sec 1</p>" in result
    # It should be skipped
    assert "Section 1" in report.skipped_sections
    assert "Section 1" not in report.updated_sections
    # Diagnostic should be recorded
    assert "Section 1" in report.diagnostics
    assert "low confidence" in report.diagnostics["Section 1"].lower()
    
    mock_ai.generate.assert_not_called()


def test_generate_updated_article_validation_retry_success() -> None:
    """Should retry generation if validation fails and succeed on retry."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">It was 2023.</p>',
        sections=[
            Section(
                name="Content",
                type="paragraph",
                astra_id="1",
                content="<p>It was 2023.</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Content",
                reason="Update",
                confidence=1.0,
                action=ActionType.UPDATE,
                required_entities=[],  # No new years allowed
            ),
        ]
    )

    mock_ai = MagicMock()
    mock_ai.generate.side_effect = [
        # Attempt 1: Fails validation (hallucinates 2024)
        "<ASTRA_HTML_START>\n<p>It is 2024.</p>\n<ASTRA_HTML_END>",
        # Attempt 2: Succeeds validation
        "<ASTRA_HTML_START>\n<p>It was 2023.</p>\n<ASTRA_HTML_END>",
    ]

    result, report = generate_updated_article(article, plan, mock_ai)

    assert mock_ai.generate.call_count == 2
    assert report.updated_sections == ["Content"]
    # We should have a warning about the first attempt failing
    assert any("Validation failed" in w for w in report.warnings) is False # wait, warnings are only added if attempt == MAX_RETRIES. It succeeded on attempt 2!
    assert "<p>It was 2023.</p>" in result


def test_generate_updated_article_validation_retry_failure() -> None:
    """Should exhaust retries, fallback to original HTML, and log diagnostic."""
    article = Article(
        title="Test",
        raw_html='<p data-astra-id="1">It was 2023.</p>',
        sections=[
            Section(
                name="Content",
                type="paragraph",
                astra_id="1",
                content="<p>It was 2023.</p>",
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Content",
                reason="Update",
                confidence=1.0,
                action=ActionType.UPDATE,
                required_entities=[],  # No new years allowed
            ),
        ]
    )

    mock_ai = MagicMock()
    # Fails all attempts by hallucinating 2024
    mock_ai.generate.side_effect = [
        "<ASTRA_HTML_START>\n<p>It is 2024.</p>\n<ASTRA_HTML_END>",
        "<ASTRA_HTML_START>\n<p>It is still 2024.</p>\n<ASTRA_HTML_END>",
        "<ASTRA_HTML_START>\n<p>Definitely 2024.</p>\n<ASTRA_HTML_END>",
    ]

    result, report = generate_updated_article(article, plan, mock_ai)

    assert mock_ai.generate.call_count == 3
    assert "Content" in report.skipped_sections
    assert "Content" not in report.updated_sections
    assert "Content" in report.diagnostics
    assert "hallucinated" in report.diagnostics["Content"]
    assert any("Validation failed after 2 retries" in w for w in report.warnings)
    # Reverts to original HTML
    assert "<p>It was 2023.</p>" in result


def test_generate_full_article_update_success() -> None:
    """Should send full article + plan to AI and parse ASTRA markers."""
    from app.application.generator import generate_full_article_update

    original_html = "<h1>Title</h1><p>Old content</p>"
    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section="Intro",
                reason="Needs SEO",
                confidence=0.85,
                action=ActionType.UPDATE,
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
    assert report.confidence_score == 0.85
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
            SectionDecision(
                section="Intro",
                reason="Needs update",
                confidence=0.90,
                action=ActionType.UPDATE,
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
            SectionDecision(
                section="Intro",
                reason="Update SEO",
                confidence=0.80,
                action=ActionType.UPDATE,
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
            SectionDecision(
                section="Intro",
                reason="Update SEO",
                confidence=0.80,
                action=ActionType.UPDATE,
            ),
            SectionDecision(
                section="FAQ",
                reason="OK as-is",
                confidence=0.95,
                action=ActionType.SKIP,
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
    assert report.confidence_score == 0.80


def test_generate_updated_article_preserves_structure() -> None:
    """Should preserve attributes of target tag when updating."""
    article = Article(
        title="Test",
        raw_html='<p id="p1" class="date-txt" data-astra-id="1">Old Date</p>',
        sections=[
            Section(
                name="Date",
                type="paragraph",
                astra_id="1",
                content='<p id="p1" class="date-txt">Old Date</p>',
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Date",
                reason="Update date",
                confidence=1.0,
                action=ActionType.UPDATE,
            ),
        ]
    )

    mock_ai = MagicMock()
    # AI strips attributes on attempt 1, then fixes it on attempt 2
    mock_ai.generate.side_effect = [
        "<ASTRA_HTML_START>\n<p>New Date</p>\n<ASTRA_HTML_END>",
        '<ASTRA_HTML_START>\n<p id="p1" class="date-txt">New Date</p>\n<ASTRA_HTML_END>'
    ]

    result, report = generate_updated_article(article, plan, mock_ai)

    assert 'class="date-txt"' in result
    assert 'id="p1"' in result
    assert "New Date" in result
    
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
                type="paragraph",
                astra_id="1",
                content='<p>Content</p>',
            ),
        ],
    )

    plan = UpdatePlan(
        actions=[
            SectionDecision(
                section_id="1",
                section="Content",
                reason="Update",
                confidence=1.0,
                action=ActionType.UPDATE,
            ),
        ]
    )

    mock_ai = MagicMock()
    mock_ai.generate.return_value = (
        "<ASTRA_HTML_START>\n"
        "```html\n"
        "<p>Updated Content</p>\n"
        "```\n"
        "<ASTRA_HTML_END>"
    )

    result, report = generate_updated_article(article, plan, mock_ai)

    assert "<p>Updated Content</p>" in result
    assert "```html" not in result
    assert "```" not in result
    assert report.updated_sections == ["Content"]
