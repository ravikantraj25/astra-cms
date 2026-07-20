"""Tests for the prompt builder."""

from __future__ import annotations

from app.application.prompt_builder import (
    _detect_article_type,
    build_analysis_prompt,
    build_prompt,
)
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
                astra_id="1",
                content="Intro text",
            ),
            Section(
                name="Conclusion",
                type="conclusion",
                astra_id="2",
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

    assert "DEEP ARTICLE ANALYSIS" in prompt
    assert "Title: Analysis Article" in prompt
    assert "Word Count: 4" in prompt
    assert "section_decisions" in prompt
    assert "DECISION RULES" in prompt
    assert "STRICT JSON" in prompt


def test_build_full_article_update_prompt() -> None:
    """It should embed original HTML and update plan into the template."""
    from app.application.prompt_builder import build_full_article_update_prompt

    html = "<h1>Hello World</h1><p>Content here.</p>"
    plan_json = '{"actions": [{"section": "Intro", "action": "Update"}]}'

    prompt = build_full_article_update_prompt(html, plan_json)

    # Assert placeholders are replaced
    assert "{{ORIGINAL_HTML}}" not in prompt
    assert "{{UPDATE_PLAN_JSON}}" not in prompt

    # Assert actual content is present
    assert "<h1>Hello World</h1><p>Content here.</p>" in prompt
    assert '"section": "Intro"' in prompt

    # Assert output contract instructions are present
    assert "<ASTRA_HTML_START>" in prompt
    assert "<ASTRA_HTML_END>" in prompt
    assert "NON-NEGOTIABLE RULES" in prompt
    assert "PRESERVE EXACTLY" in prompt
    assert "OUTPUT CONTRACT" in prompt


def test_extract_astra_html_with_markers() -> None:
    """It should extract HTML between ASTRA markers."""
    from app.application.prompt_builder import extract_astra_html

    response = "<ASTRA_HTML_START>\n<h1>Updated</h1>\n<ASTRA_HTML_END>"
    assert extract_astra_html(response) == "<h1>Updated</h1>"


def test_extract_astra_html_with_surrounding_text() -> None:
    """It should ignore text outside the markers."""
    from app.application.prompt_builder import extract_astra_html

    response = "Some preamble\n<ASTRA_HTML_START>\n<p>Clean</p>\n<ASTRA_HTML_END>\nSome epilogue"
    assert extract_astra_html(response) == "<p>Clean</p>"


def test_extract_astra_html_fallback_markdown() -> None:
    """It should strip markdown fences when markers are absent."""
    from app.application.prompt_builder import extract_astra_html

    response = "```html\n<p>Fallback</p>\n```"
    assert extract_astra_html(response) == "<p>Fallback</p>"


def test_extract_astra_html_fallback_plain() -> None:
    """It should return the cleaned text when no markers or fences exist."""
    from app.application.prompt_builder import extract_astra_html

    response = "  <div>Plain</div>  "
    assert extract_astra_html(response) == "<div>Plain</div>"


def test_extract_astra_html_empty_raises() -> None:
    """It should raise ValueError when markers exist but content is empty."""
    from app.application.prompt_builder import extract_astra_html

    import pytest

    response = "<ASTRA_HTML_START>\n\n<ASTRA_HTML_END>"
    with pytest.raises(ValueError, match="empty HTML"):
        extract_astra_html(response)


def test_prompt_builder_class() -> None:
    """PromptBuilder should load the template file and substitute placeholders."""
    from app.application.prompt_builder import PromptBuilder

    builder = PromptBuilder()

    html = "<h1>Test</h1>"
    plan_json = '{"actions": []}'

    prompt = builder.build(html, plan_json)

    assert "{{ORIGINAL_HTML}}" not in prompt
    assert "{{UPDATE_PLAN_JSON}}" not in prompt
    assert "<h1>Test</h1>" in prompt
    assert '{"actions": []}' in prompt
    assert "<ASTRA_HTML_START>" in prompt
    assert "OUTPUT CONTRACT" in prompt


def test_prompt_builder_class_custom_template(tmp_path) -> None:
    """PromptBuilder should accept a custom template path."""
    from app.application.prompt_builder import PromptBuilder

    template = tmp_path / "custom.txt"
    template.write_text(
        "ARTICLE: {{ORIGINAL_HTML}}\nPLAN: {{UPDATE_PLAN_JSON}}",
        encoding="utf-8",
    )

    builder = PromptBuilder(template_path=template)
    result = builder.build("<p>Hi</p>", '{"a":1}')

    assert result == 'ARTICLE: <p>Hi</p>\nPLAN: {"a":1}'
