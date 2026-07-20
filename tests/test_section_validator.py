"""Tests for SectionValidator."""

from __future__ import annotations

import pytest

from app.application.section_validator import SectionValidator
from app.domain.plan import SectionDecision, ActionType


def _make_decision(required: list[str]) -> SectionDecision:
    return SectionDecision(
        section_id="1",
        section="Intro",
        action=ActionType.UPDATE,
        reason="Update",
        confidence=1.0,
        required_entities=required,
    )


def test_validate_html_empty() -> None:
    original = "<p>Test</p>"
    updated = "   "
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("empty" in r for r in result.failed_rules)


def test_validate_html_dangerous_tags() -> None:
    original = "<p>Test</p>"
    updated = "<p>Test</p><script>alert(1)</script>"
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("script" in r.lower() for r in result.failed_rules)


def test_validate_html_dangerous_attributes() -> None:
    original = "<p>Test</p>"
    updated = "<a href=\"javascript:alert(1)\">Link</a><p onclick=\"foo()\">Test</p>"
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("onclick" in r.lower() for r in result.failed_rules)
    assert any("javascript" in r.lower() for r in result.failed_rules)


def test_validate_years_hallucinated() -> None:
    original = "<p>It was 2023.</p>"
    updated = "<p>It is 2024 now.</p>"
    decision = _make_decision([]) # 2024 is not allowed
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("2024" in r for r in result.failed_rules)


def test_validate_years_allowed() -> None:
    original = "<p>It was 2023.</p>"
    updated = "<p>It is 2024 now.</p>"
    decision = _make_decision(["2024"])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert result.is_valid


def test_validate_dates_hallucinated() -> None:
    original = "<p>Event in January.</p>"
    updated = "<p>Event moved to February.</p>"
    decision = _make_decision([]) 
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("February" in r for r in result.failed_rules)


def test_validate_dates_allowed() -> None:
    original = "<p>Event in January.</p>"
    updated = "<p>Event moved to February.</p>"
    decision = _make_decision(["February"]) 
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert result.is_valid


def test_validate_links_removed() -> None:
    original = "<p><a href='/home'>Home</a> and <a href='/about'>About</a></p>"
    updated = "<p><a href='/home'>Home</a> only</p>"
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("'/about'" in r for r in result.failed_rules)


def test_validate_images_removed() -> None:
    original = "<img src='img1.jpg'><img src='img2.jpg'>"
    updated = "<img src='img1.jpg'>"
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("'img2.jpg'" in r for r in result.failed_rules)


def test_validate_headings_changed() -> None:
    original = "<h2>Title</h2><p>Text</p>"
    updated = "<h3>Title</h3><p>Text</p>"
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("Heading structure" in r for r in result.failed_rules)


def test_validate_schema_removed() -> None:
    original = "<div class='container' id='main' itemscope itemtype='http://schema.org/Event'><p itemprop='name'>Event</p></div>"
    updated = "<div class='container'><p>Event</p></div>"
    decision = _make_decision([])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    # Multiple rules should fail (id, itemscope, itemtype, itemprop)
    assert len(result.failed_rules) >= 4


def test_validate_required_updates() -> None:
    original = "<p>Text</p>"
    updated = "<p>Text with 2025</p>"
    decision = _make_decision(["2025", "October"])
    
    result = SectionValidator.validate(original, updated, decision)
    
    assert not result.is_valid
    assert any("October" in r for r in result.failed_rules)
