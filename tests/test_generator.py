"""Tests for HTML generation logic."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.application.generator import generate_updated_article
from app.domain.article import Article, Section
from app.domain.plan import UpdateAction, UpdatePlan


def test_generate_updated_article_skips_and_deletes() -> None:
    """Should correctly skip and delete sections without calling AI."""
    article = Article(
        title="Test",
        raw_html="<p>Sec 1</p><p>Sec 2</p>",
        sections=[
            Section(
                name="Section 1",
                type="Paragraph",
                start_position=0,
                end_position=12,
                content="<p>Sec 1</p>",
            ),
            Section(
                name="Section 2",
                type="Paragraph",
                start_position=12,
                end_position=24,
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

    result = generate_updated_article(article, plan, mock_ai)

    assert result == "<p>Sec 1</p>"
    mock_ai.generate.assert_not_called()


def test_generate_updated_article_updates() -> None:
    """Should call AI for Update actions and replace HTML backwards."""
    article = Article(
        title="Test",
        raw_html="<p>Sec 1</p><p>Sec 2</p>",
        sections=[
            Section(
                name="Section 1",
                type="Paragraph",
                start_position=0,
                end_position=12,
                content="<p>Sec 1</p>",
            ),
            Section(
                name="Section 2",
                type="Paragraph",
                start_position=12,
                end_position=24,
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
                confidence=90,
                action="Update",
            ),
        ]
    )

    mock_ai = MagicMock()
    # The generator sorts descending, so Section 2 is processed first, then Section 1.
    mock_ai.generate.side_effect = [
        "```html\n<p>New Sec 2</p>\n```",
        "<p>New Sec 1</p>",
    ]

    result = generate_updated_article(article, plan, mock_ai)

    assert result == "<p>New Sec 1</p><p>New Sec 2</p>"
    assert mock_ai.generate.call_count == 2
