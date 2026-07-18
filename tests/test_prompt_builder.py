"""Tests for the prompt builder."""

from __future__ import annotations

from app.application.prompt_builder import _detect_article_type, build_prompt, build_analysis_prompt
from app.domain.article import Article, Section


def test_detect_article_type() -> None:
    """It should correctly detect article types based on headings."""
    assert (
        _detect_article_type(Article(headings=["Frequently Asked Questions"]))
        == "FAQ / Knowledge-Base Article"
    )
    assert (
        _detect_article_type(Article(headings=["Event Schedule", "Venue Location"]))
        == "Event Page"
    )
    assert (
        _detect_article_type(Article(headings=["How to Build a CMS", "Step 1"]))
        == "Tutorial / How-To Guide"
    )
    assert (
        _detect_article_type(Article(headings=["Next.js vs Remix", "Comparison"]))
        == "Review / Comparison"
    )
    assert _detect_article_type(Article(headings=["Press Release 2026"])) == "News / Press Release"
    assert _detect_article_type(Article(headings=["Random Topic"])) == "General Article"


def test_build_prompt() -> None:
    """It should build a well-formatted prompt string."""
    article = Article(
        title="Test Article",
        meta_description="A test article for prompt building.",
        headings=["Introduction", "Conclusion"],
        paragraphs=["This is a paragraph."],
        sections=[
            Section(
                name="Intro",
                type="introduction",
                start_position=0,
                end_position=10,
                content="Intro text",
            ),
            Section(
                name="Conclusion",
                type="conclusion",
                start_position=20,
                end_position=30,
                content="End text",
            ),
        ],
    )

    prompt = build_prompt(article)

    # Assert specific sections are present
    assert "ARTICLE UPDATE PROMPT" in prompt
    assert "Title: Test Article" in prompt
    assert "Word Count: 6" in prompt
    assert "Meta Description: A test article for prompt building." in prompt

    # Assert detected sections are listed
    assert "1. [introduction] Intro" in prompt
    assert "2. [conclusion] Conclusion" in prompt

    # Assert headings are listed
    assert "- Introduction" in prompt
    assert "- Conclusion" in prompt

    # Assert update instructions are present
    assert "UPDATE INSTRUCTIONS" in prompt
    assert "Return the updated article as valid HTML." in prompt


def test_build_analysis_prompt() -> None:
    """It should build a well-formatted analysis prompt string."""
    article = Article(
        title="Analysis Article",
        headings=["H1", "H2"],
        paragraphs=["P1", "P2"],
        images=[],
        links=[],
    )

    prompt = build_analysis_prompt(article)

    assert "ARTICLE ANALYSIS PROMPT" in prompt
    assert "Title: Analysis Article" in prompt
    assert "Word Count: 4" in prompt
    assert "Headings: H1, H2" in prompt
    assert "Number of paragraphs: 2" in prompt
    assert "Number of images: 0" in prompt
    assert "EXACTLY as a valid JSON object matching this schema" in prompt
