"""Tests for the AI response validator."""

from __future__ import annotations

import pytest

from app.application.response_validator import validate_ai_response


def test_valid_response() -> None:
    """A clean response with proper markers should return the inner HTML."""
    response = "<ASTRA_HTML_START>\n<h1>Hello</h1><p>World</p>\n<ASTRA_HTML_END>"
    result = validate_ai_response(response)
    assert result == "<h1>Hello</h1><p>World</p>"


def test_reasoning_before_html_rejected() -> None:
    """Text before the start marker should be rejected."""
    response = (
        "Here is my reasoning about the changes.\n"
        "<ASTRA_HTML_START>\n<h1>Title</h1>\n<ASTRA_HTML_END>"
    )
    with pytest.raises(RuntimeError, match="non-whitespace content outside"):
        validate_ai_response(response)


def test_reasoning_after_html_rejected() -> None:
    """Text after the end marker should be rejected."""
    response = (
        "<ASTRA_HTML_START>\n<h1>Title</h1>\n<ASTRA_HTML_END>\n"
        "I hope this helps! Let me know if you need more changes."
    )
    with pytest.raises(RuntimeError, match="non-whitespace content outside"):
        validate_ai_response(response)


def test_markdown_fences_cleaned() -> None:
    """Markdown code fences inside the markers should be cleaned."""
    response = (
        "<ASTRA_HTML_START>\n"
        "```html\n<h1>Title</h1>\n```\n"
        "<ASTRA_HTML_END>"
    )
    result = validate_ai_response(response)
    assert result == "<h1>Title</h1>"


def test_malformed_html_rejected() -> None:
    """Pure text with no HTML tags should be rejected."""
    response = (
        "<ASTRA_HTML_START>\n"
        "This is just plain text with no tags at all.\n"
        "<ASTRA_HTML_END>"
    )
    with pytest.raises(RuntimeError, match="does not contain valid HTML"):
        validate_ai_response(response)


def test_missing_delimiters() -> None:
    """A response without ASTRA markers should be rejected."""
    response = "<h1>Title</h1><p>Content</p>"
    with pytest.raises(RuntimeError, match="exactly one"):
        validate_ai_response(response)


def test_empty_response() -> None:
    """An empty string should be rejected."""
    with pytest.raises(RuntimeError, match="empty response"):
        validate_ai_response("")


def test_whitespace_only_response() -> None:
    """A whitespace-only string should be rejected."""
    with pytest.raises(RuntimeError, match="empty response"):
        validate_ai_response("   \n\t  ")


def test_empty_between_markers() -> None:
    """Markers present but nothing between them should be rejected."""
    response = "<ASTRA_HTML_START>\n\n<ASTRA_HTML_END>"
    with pytest.raises(RuntimeError, match="empty HTML"):
        validate_ai_response(response)


def test_contamination_section_update() -> None:
    """Banned phrase 'SECTION UPDATE' inside content should be rejected."""
    response = (
        "<ASTRA_HTML_START>\n"
        "<h2>SECTION UPDATE</h2><p>New content</p>\n"
        "<ASTRA_HTML_END>"
    )
    with pytest.raises(RuntimeError, match="banned phrase"):
        validate_ai_response(response)


def test_context_sensitive_certainly_passes() -> None:
    """Context-sensitive phrase 'Certainly' should pass response_validator.

    These are caught later by QualityValidator when comparing original vs updated.
    """
    response = (
        "<ASTRA_HTML_START>\n"
        "<p>Certainly, this festival is celebrated widely.</p>\n"
        "<ASTRA_HTML_END>"
    )
    result = validate_ai_response(response)
    assert "<p>" in result


def test_context_sensitive_explanation_passes() -> None:
    """Context-sensitive phrase 'Explanation:' should pass response_validator."""
    response = (
        "<ASTRA_HTML_START>\n"
        "<p>Explanation: I changed the title.</p>\n"
        "<ASTRA_HTML_END>"
    )
    result = validate_ai_response(response)
    assert "<p>" in result


def test_context_sensitive_note_passes() -> None:
    """Context-sensitive phrase 'Note:' should pass response_validator."""
    response = (
        "<ASTRA_HTML_START>\n"
        "<p>Note: This section was rewritten.</p>\n"
        "<ASTRA_HTML_END>"
    )
    result = validate_ai_response(response)
    assert "<p>" in result


def test_context_sensitive_reason_passes() -> None:
    """Context-sensitive phrase 'Reason:' should pass response_validator."""
    response = (
        "<ASTRA_HTML_START>\n"
        "<p>Reason: Outdated information.</p><h1>Title</h1>\n"
        "<ASTRA_HTML_END>"
    )
    result = validate_ai_response(response)
    assert "<h1>" in result


def test_context_sensitive_sure_passes() -> None:
    """Context-sensitive phrase 'Sure' should pass response_validator."""
    response = (
        "<ASTRA_HTML_START>\n"
        "<p>Sure, I can help with that.</p>\n"
        "<ASTRA_HTML_END>"
    )
    result = validate_ai_response(response)
    assert "<p>" in result


def test_contamination_updated_html() -> None:
    """Banned phrase 'UPDATED HTML' inside content should be rejected."""
    response = (
        "<ASTRA_HTML_START>\n"
        "UPDATED HTML\n<h1>Title</h1>\n"
        "<ASTRA_HTML_END>"
    )
    with pytest.raises(RuntimeError, match="banned phrase"):
        validate_ai_response(response)
