"""Production quality validator for AI-generated HTML.

Checks:
    1. HTML validity
    2. Prompt leakage (always-banned + context-sensitive)
    3. Year mismatch (title says 2026, body still says 2025)
    4. Dangerous HTML (scripts, event handlers)
    5. Image preservation
    6. Table preservation
    7. Link preservation
    8. Structure preservation (headings, classes, IDs, Gutenberg)
"""

from __future__ import annotations

import collections
import re

from bs4 import BeautifulSoup, Comment

from app.domain.validation import QualityReport

_DANGEROUS_TAGS = {"script", "object", "embed", "applet"}

# Phrases that are NEVER legitimate in article HTML — always indicate AI leakage.
_ALWAYS_BANNED_PHRASES = [
    "SECTION UPDATE",
    "UPDATED HTML",
    "ASTRA_HTML_START",
    "ASTRA_HTML_END",
    "```html",
    "```markdown",
    "```",
    "Here is the updated",
    "I updated",
    "Changes made",
]

# Phrases that are common in AI chat responses but also appear naturally in
# article content.  Only flagged when *newly introduced*.
_CONTEXT_SENSITIVE_PHRASES = [
    "Reason:",
    "Explanation:",
    "Note:",
    "Sure",
    "Certainly",
]

# Regex to find 4-digit years in text.
_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_title_year(html: str) -> int | None:
    """Extract the year from the first <h1> tag, if present."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1:
        match = _YEAR_PATTERN.search(h1.get_text())
        if match:
            return int(match.group(1))
    return None


def _check_year_mismatch(updated_html: str) -> bool:
    """Return True if the title year and body years are contradictory.

    Example failure: title says "2026" but body paragraphs still say "2025".
    This ignores historical dates (like 2021) by only checking for (title_year - 1).
    """
    title_year = _extract_title_year(updated_html)
    if not title_year:
        return False

    soup = BeautifulSoup(updated_html, "html.parser")
    
    # Remove h1 so we don't re-match it in the body scan
    h1 = soup.find("h1")
    if h1:
        h1.decompose()

    # Scan body text (excluding h1) for the immediately preceding year
    body_text = soup.get_text()
    previous_year = title_year - 1
    
    for match in _YEAR_PATTERN.finditer(body_text):
        found_year = int(match.group(1))
        if found_year == previous_year:
            return True

    return False


def _get_links(soup: BeautifulSoup) -> list[str]:
    """Extract all href values from anchor tags in order."""
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        links.append(
            "".join(href).strip() if isinstance(href, list) else str(href).strip()
        )
    return links


def _get_structure_fingerprint(
    soup: BeautifulSoup,
) -> tuple[int, set[str], set[str], int]:
    """Extract structural metadata: heading count, classes, IDs, Gutenberg comments."""
    headings = len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
    classes: set[str] = set()
    ids: set[str] = set()

    for tag in soup.find_all(True):
        if tag.get("id"):
            val = tag["id"]
            if isinstance(val, list):
                ids.update(val)
            else:
                ids.add(str(val))
        if tag.get("class"):
            val = tag["class"]
            if isinstance(val, list):
                classes.update(val)
            else:
                classes.add(str(val))

    gutenberg = sum(
        1
        for c in soup.find_all(
            string=lambda text: isinstance(text, Comment)
        )
        if "wp:" in str(c)
    )
    return headings, classes, ids, gutenberg


# ── Main validator ───────────────────────────────────────────────────────────


class QualityValidator:
    """Validates updated HTML against the original to prevent corruption."""

    @classmethod
    def validate(cls, original_html: str, updated_html: str) -> QualityReport:
        """Run all quality checks and return a comprehensive report."""
        report = QualityReport(
            status="PASS",
            html_valid=True,
            prompt_leakage=False,
            dangerous_html=False,
            images_preserved=True,
            links_preserved=True,
            tables_preserved=True,
            structure_preserved=True,
            year_mismatch=False,
            word_diff=0,
            html_diff_percent=0.0,
            ready_to_publish=True,
        )

        original_soup = BeautifulSoup(original_html, "html.parser")
        updated_soup = BeautifulSoup(updated_html, "html.parser")

        # 1. HTML Validity
        if not updated_soup.find(True):
            report.html_valid = False

        # 2. Prompt Leakage
        lower_updated = updated_html.lower()
        lower_original = original_html.lower()

        for phrase in _ALWAYS_BANNED_PHRASES:
            if phrase.lower() in lower_updated:
                report.prompt_leakage = True
                break

        if not report.prompt_leakage:
            for phrase in _CONTEXT_SENSITIVE_PHRASES:
                p_lower = phrase.lower()
                if p_lower in lower_updated and p_lower not in lower_original:
                    report.prompt_leakage = True
                    break

        # 3. Year Mismatch
        report.year_mismatch = _check_year_mismatch(updated_html)

        # 4. Dangerous HTML
        for tag in updated_soup.find_all(True):
            if report.dangerous_html:
                break
                
            if tag.name in _DANGEROUS_TAGS:
                report.dangerous_html = True
            elif tag.name == "iframe":
                src_val = tag.get("src", "")
                if isinstance(src_val, list):
                    src = "".join(src_val).lower()
                else:
                    src = str(src_val if src_val is not None else "").lower()
                if "youtube" not in src and "vimeo" not in src:
                    report.dangerous_html = True

            for attr, val in tag.attrs.items():
                attr_lower = attr.lower()
                if attr_lower.startswith("on"):
                    report.dangerous_html = True
                    break
                elif attr_lower in ("href", "src"):
                    val_str = (
                        "".join(val).lower()
                        if isinstance(val, list)
                        else str(val).lower()
                    )
                    if val_str.startswith("javascript:") or val_str.startswith(
                        "vbscript:"
                    ):
                        report.dangerous_html = True
                        break

        # 5. Images preserved
        def _get_image_srcs(soup: BeautifulSoup) -> list[str]:
            return [
                str(img.get("src", ""))
                for img in soup.find_all("img")
            ]
            
        orig_img_counts = collections.Counter(_get_image_srcs(original_soup))
        upd_img_counts = collections.Counter(_get_image_srcs(updated_soup))
        for img, count in orig_img_counts.items():
            if upd_img_counts[img] < count:
                report.images_preserved = False
                break

        # 6. Tables preserved
        if len(original_soup.find_all("table")) != len(
            updated_soup.find_all("table")
        ):
            report.tables_preserved = False

        # 7. Links preserved
        orig_link_counts = collections.Counter(_get_links(original_soup))
        upd_link_counts = collections.Counter(_get_links(updated_soup))
        for link, count in orig_link_counts.items():
            if upd_link_counts[link] < count:
                report.links_preserved = False
                break

        # 8. Structure preserved
        (
            orig_headings,
            orig_classes,
            orig_ids,
            orig_gutenberg,
        ) = _get_structure_fingerprint(original_soup)
        (
            upd_headings,
            upd_classes,
            upd_ids,
            upd_gutenberg,
        ) = _get_structure_fingerprint(updated_soup)

        if orig_headings != upd_headings:
            report.structure_preserved = False
        if orig_gutenberg > 0 and upd_gutenberg < orig_gutenberg:
            report.structure_preserved = False
        if orig_classes - upd_classes:
            report.structure_preserved = False
        if orig_ids - upd_ids:
            report.structure_preserved = False

        # 9. Statistics
        orig_words = len(original_soup.get_text().split())
        upd_words = len(updated_soup.get_text().split())
        report.word_diff = upd_words - orig_words

        orig_len = len(original_html.encode("utf-8"))
        upd_len = len(updated_html.encode("utf-8"))
        if orig_len > 0:
            report.html_diff_percent = round(
                ((upd_len - orig_len) / orig_len) * 100, 2
            )
        else:
            report.html_diff_percent = 100.0

        # ── Overall Status ────────────────────────────────────────────────
        is_valid = (
            report.html_valid
            and not report.prompt_leakage
            and not report.dangerous_html
            and not report.year_mismatch
            and report.images_preserved
            and report.links_preserved
            and report.tables_preserved
            and report.structure_preserved
        )

        if not is_valid:
            report.status = "FAIL"
            report.ready_to_publish = False

        return report
