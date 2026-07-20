"""Tests for the prompt builder."""

from datetime import datetime

import pytest

from app.domain.article import Article, Section
from app.domain.intelligence import ArticleAnalysis, ArticleType, ContentFreshness, UpdateDecision, TemporalEntity, UpdatePolicy
from app.domain.plan import SectionDecision, ActionType
from app.application.prompt_builder import (
    build_planner_prompt,
    build_section_update_prompt,
    _truncate_html,
    _detect_article_type
)


def test_truncate_html_fits():
    html = "<p>Short html</p>"
    truncated = _truncate_html(html, max_chars=100)
    assert truncated == html


def test_truncate_html_cuts_off_safely():
    html = "<div><p>Paragraph 1</p><p>Paragraph 2</p></div>"
    truncated = _truncate_html(html, max_chars=30)
    # The first paragraph should fit, but the second might not
    assert "Paragraph 1" in truncated
    assert "Paragraph 2" not in truncated
    # Must be valid HTML
    assert truncated.startswith("<div><p>Paragraph 1</p>")
    assert "[TRUNCATED]" in truncated


def test_detect_article_type():
    article_faq = Article(headings=["FAQ about Event"])
    assert _detect_article_type(article_faq) == "FAQ / Knowledge-Base Article"
    
    article_news = Article(headings=["Press Release 2024"])
    assert _detect_article_type(article_news) == "News / Press Release"


def test_build_planner_prompt_includes_intelligence():
    article = Article(
        title="My Event",
        raw_html="<p data-astra-id='1'>Text</p>",
        sections=[Section(name="Content", type="paragraph", astra_id="1", content="<p data-astra-id='1'>Text</p>")]
    )
    
    intelligence = ArticleAnalysis(
        article_type=ArticleType.ANNUAL_EVENT,
        freshness=ContentFreshness.RECURRING_EVENT,
        decision=UpdateDecision(
            strategy="Selective",
            reason="It is an annual event."
        ),
        temporal_entities=[
            TemporalEntity(
                entity="2024",
                policy=UpdatePolicy.UPDATE,
                reason="Needs new year",
                confidence=0.99,
                source_sentence="Event in 2024"
            )
        ],
        historical_facts=[],
        event_info=[],
        structural_analysis=[],
        risks=[],
    )
    
    prompt = build_planner_prompt(article, intelligence)
    
    # Check that intelligence properties are injected as JSON
    assert "Annual Event" in prompt
    assert "Selective" in prompt
    assert "2024" in prompt
    # Check that sections are injected
    assert "[1] Content (Type: SectionType.PARAGRAPH)" in prompt


def test_build_section_update_prompt():
    section = Section(name="Content", type="paragraph", astra_id="1", content="<p>2024</p>")
    decision = SectionDecision(
        section_id="1",
        section="Content",
        action=ActionType.UPDATE,
        reason="Needs new year",
        confidence=0.9,
        fields_to_update=["Year"],
        fields_to_preserve=["Image"],
        forbidden_changes=["Price"],
        required_entities=["2025"],
        expected_output="Updated to 2025"
    )
    
    prompt = build_section_update_prompt(section, decision)
    
    assert "Action: Update" in prompt
    assert "FIELDS TO UPDATE:\n - Year" in prompt
    assert "FIELDS TO PRESERVE (NEVER MODIFY THESE):\n - Image" in prompt
    assert "FORBIDDEN CHANGES:\n - Price" in prompt
    assert "REQUIRED ENTITIES (MUST BE INCLUDED):\n - 2025" in prompt
    assert "<p>2024</p>" in prompt
    assert "<ASTRA_HTML_START>" in prompt
