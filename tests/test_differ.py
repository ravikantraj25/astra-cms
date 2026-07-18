"""Tests for HTML diff generation."""

from __future__ import annotations

from app.application.differ import build_diff_report
from app.domain.article import Article


def test_build_diff_report_identical() -> None:
    """Identical articles should produce no differences."""
    original = Article(
        title="Test",
        headings=["Introduction"],
        paragraphs=["This is a test."],
    )
    updated = Article(
        title="Test",
        headings=["Introduction"],
        paragraphs=["This is a test."],
    )

    report = build_diff_report(original, updated)

    assert not report.added
    assert not report.removed
    assert not report.modified


def test_build_diff_report_added_removed() -> None:
    """Should correctly identify added and removed paragraphs."""
    original = Article(
        title="Test",
        headings=[],
        paragraphs=["Para 1", "AAAAA"],
    )
    updated = Article(
        title="Test",
        headings=[],
        paragraphs=["Para 1", "ZZZZZ"],
    )

    report = build_diff_report(original, updated)

    assert len(report.removed) == 1
    assert report.removed[0].content == "AAAAA"

    assert len(report.added) == 1
    assert report.added[0].content == "ZZZZZ"
    assert not report.modified


def test_build_diff_report_modified() -> None:
    """Should identify modified paragraphs."""
    original = Article(
        title="Test",
        headings=[],
        paragraphs=["This is a very long paragraph that will be modified."],
    )
    updated = Article(
        title="Test",
        headings=[],
        paragraphs=["This is a very long paragraph that has been modified."],
    )

    report = build_diff_report(original, updated)

    assert len(report.modified) == 1
    assert "has been modified" in report.modified[0].content
    assert not report.added
    assert not report.removed
