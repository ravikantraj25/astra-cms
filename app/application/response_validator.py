"""Strict validation of AI-generated HTML responses.

Enforces the ``<ASTRA_HTML_START>`` / ``<ASTRA_HTML_END>`` output contract
and rejects any response containing reasoning, markdown, or other
non-HTML contamination before the output is written to disk.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Phrases that are NEVER legitimate inside generated HTML.
# These are purely AI-chat artifacts and will never appear in real article
# content, so they are always rejected.
_ALWAYS_BANNED_PHRASES: tuple[str, ...] = (
    "SECTION UPDATE",
    "UPDATED HTML",
    "```html",
    "```markdown",
    "```",
    "Here is the updated",
    "I updated",
    "Changes made",
)

# Common English words that AI chat responses include but that also appear
# naturally inside real articles (e.g. "Planning note:", "ensure parking").
# The response_validator runs BEFORE we have access to the original HTML, so
# we cannot do a diff here.  These phrases are therefore NOT checked in this
# layer — they are caught later by the QualityValidator which compares
# original vs. updated HTML and only flags *newly introduced* occurrences.

_START_MARKER = "<ASTRA_HTML_START>"
_END_MARKER = "<ASTRA_HTML_END>"


def validate_ai_response(raw: str) -> str:
    """Extract, validate, and return clean HTML from an AI response.

    Steps:
        1. Locate ``<ASTRA_HTML_START>`` / ``<ASTRA_HTML_END>`` markers.
        2. Reject the response if markers are missing or content is empty.
        3. Reject the response if it contains any always-banned phrase.
        4. Validate the extracted HTML with BeautifulSoup — at least one
           real tag must be present.

    Args:
        raw: The complete raw text returned by the AI provider.

    Returns:
        The clean HTML string between the markers.

    Raises:
        RuntimeError: On any validation failure.
    """
    if not raw or not raw.strip():
        raise RuntimeError("AI returned an empty response.")

    # ── 1. Extract between markers ────────────────────────────────────────
    if _START_MARKER not in raw or _END_MARKER not in raw:
        raise RuntimeError(
            f"AI response is missing required delimiters "
            f"({_START_MARKER} / {_END_MARKER})."
        )

    start = raw.index(_START_MARKER) + len(_START_MARKER)
    end = raw.index(_END_MARKER)
    html = raw[start:end].strip()

    if not html:
        raise RuntimeError("AI returned empty HTML between ASTRA markers.")

    # ── 2. Reject contamination ───────────────────────────────────────────
    html_lower = html.lower()
    for phrase in _ALWAYS_BANNED_PHRASES:
        if phrase.lower() in html_lower:
            raise RuntimeError(
                f"AI response contains banned phrase: {phrase!r}"
            )

    # ── 3. Validate HTML structure ────────────────────────────────────────
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find(True):  # no real tags at all
        raise RuntimeError(
            "AI response does not contain valid HTML "
            "(no tags found after parsing)."
        )

    return html
