"""Application logic for generating an HTML diff report."""

from __future__ import annotations

import difflib

from app.domain.article import Article
from app.domain.diff import DiffAction, DiffReport


def build_diff_report(original: Article, updated: Article) -> DiffReport:
    """Compare two Articles and generate a DiffReport.

    Extracts paragraphs and headings in order (simplified for this heuristic)
    and uses difflib to identify added, removed, and modified blocks.

    Args:
        original: The original parsed Article.
        updated: The AI-updated parsed Article.

    Returns:
        A populated :class:`DiffReport`.
    """
    # Combine headings and paragraphs into a flat list of strings for comparison.
    # In a real-world scenario, we'd preserve the DOM order, but our Article model
    # currently splits them. We will compare headings and paragraphs separately.

    report = DiffReport(added=[], removed=[], modified=[])

    _compare_lists(
        original.headings,
        updated.headings,
        "Heading",
        report,
    )

    _compare_lists(
        original.paragraphs,
        updated.paragraphs,
        "Paragraph",
        report,
    )

    return report


def _compare_lists(
    old_items: list[str],
    new_items: list[str],
    element_type: str,
    report: DiffReport,
) -> None:
    """Compare two lists of strings and append DiffActions to the report."""
    matcher = difflib.SequenceMatcher(None, old_items, new_items)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            # Heuristic: If they are similar length, treat as pairs of modified.
            # Otherwise, just log them as bulk replaced (modified).
            old_text = " ".join(old_items[i1:i2])
            new_text = " ".join(new_items[j1:j2])

            # Use SequenceMatcher on characters to get a confidence score based on similarity
            similarity = difflib.SequenceMatcher(None, old_text, new_text).ratio()

            if similarity < 0.3:
                # If they are completely different, treat as remove + add
                for text in old_items[i1:i2]:
                    report.removed.append(
                        DiffAction(
                            type="Removed",
                            content=text[:100] + ("..." if len(text) > 100 else ""),
                            confidence=95.0,
                            reason=f"Original {element_type.lower()} was completely replaced.",
                        )
                    )
                for text in new_items[j1:j2]:
                    report.added.append(
                        DiffAction(
                            type="Added",
                            content=text[:100] + ("..." if len(text) > 100 else ""),
                            confidence=95.0,
                            reason=f"New {element_type.lower()} completely replaced original.",
                        )
                    )
            else:
                report.modified.append(
                    DiffAction(
                        type="Modified",
                        content=new_text[:100] + ("..." if len(new_text) > 100 else ""),
                        confidence=round(similarity * 100, 1),
                        reason=f"{element_type} was rewritten or altered.",
                    )
                )
        elif tag == "delete":
            for text in old_items[i1:i2]:
                report.removed.append(
                    DiffAction(
                        type="Removed",
                        content=text[:100] + ("..." if len(text) > 100 else ""),
                        confidence=95.0,
                        reason=f"Original {element_type.lower()} is missing in the update.",
                    )
                )
        elif tag == "insert":
            for text in new_items[j1:j2]:
                report.added.append(
                    DiffAction(
                        type="Added",
                        content=text[:100] + ("..." if len(text) > 100 else ""),
                        confidence=95.0,
                        reason=f"New {element_type.lower()} introduced by AI.",
                    )
                )
