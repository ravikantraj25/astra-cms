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
        1. Pre-clean markdown fences using regex.
        2. Locate exactly one ``<ASTRA_HTML_START>`` and one ``<ASTRA_HTML_END>`` marker.
        3. Reject the response if content exists outside the markers.
        4. Reject the response if it contains any always-banned phrase.
        5. Validate the extracted HTML with BeautifulSoup — at least one
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

    # ── Pre-clean common markdown fence contamination ─────────────────────
    raw = re.sub(r"```(?:html|markdown)?[\r\n]*", "", raw, flags=re.IGNORECASE)

    # ── 1. Strict extraction between markers ──────────────────────────────
    start_count = raw.count(_START_MARKER)
    end_count = raw.count(_END_MARKER)

    if start_count != 1 or end_count != 1:
        raise RuntimeError(
            f"AI response must contain exactly one {_START_MARKER} and one {_END_MARKER}. "
            f"Found {start_count} start(s) and {end_count} end(s)."
        )

    start_idx = raw.index(_START_MARKER)
    end_idx = raw.index(_END_MARKER)

    if start_idx >= end_idx:
        raise RuntimeError(f"{_START_MARKER} must appear before {_END_MARKER}.")

    # ── 2. Reject content outside markers ─────────────────────────────────
    pre_content = raw[:start_idx].strip()
    post_content = raw[end_idx + len(_END_MARKER):].strip()

    if pre_content or post_content:
        raise RuntimeError("AI response contains non-whitespace content outside the ASTRA markers.")

    html = raw[start_idx + len(_START_MARKER):end_idx].strip()

    if not html:
        raise RuntimeError("AI returned empty HTML between ASTRA markers.")

    # ── 3. Reject contamination inside HTML ───────────────────────────────
    html_lower = html.lower()
    for phrase in _ALWAYS_BANNED_PHRASES:
        if phrase.lower() in html_lower:
            raise RuntimeError(
                f"AI response contains banned phrase: {phrase!r}"
            )

    # ── 4. Validate HTML structure ────────────────────────────────────────
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find(True):  # no real tags at all
        raise RuntimeError(
            "AI response does not contain valid HTML "
            "(no tags found after parsing)."
        )

    return html
