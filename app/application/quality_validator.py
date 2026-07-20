"""Production quality validator for AI-generated HTML."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

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
# article content (e.g. "Planning note:", "ensure parking").  These are only
# flagged when they are *newly introduced* — i.e. present in the updated HTML
# but absent from the original.
_CONTEXT_SENSITIVE_PHRASES = [
    "Reason:",
    "Explanation:",
    "Note:",
    "Sure",
    "Certainly",
]


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

        # Always-banned phrases: flag if present anywhere in the output
        for phrase in _ALWAYS_BANNED_PHRASES:
            if phrase.lower() in lower_updated:
                report.prompt_leakage = True
                break

        # Context-sensitive phrases: only flag if NEWLY INTRODUCED by the AI
        # (present in updated but not in original)
        if not report.prompt_leakage:
            for phrase in _CONTEXT_SENSITIVE_PHRASES:
                p_lower = phrase.lower()
                if p_lower in lower_updated and p_lower not in lower_original:
                    report.prompt_leakage = True
                    break

        # 3. Dangerous HTML
        for tag in updated_soup.find_all(True):
            if tag.name in _DANGEROUS_TAGS:
                report.dangerous_html = True
            elif tag.name == "iframe":
                src = tag.get("src", "").lower()
                if "youtube" not in src and "vimeo" not in src:
                    report.dangerous_html = True
            
            for attr, val in tag.attrs.items():
                attr_lower = attr.lower()
                if attr_lower.startswith("on"):
                    report.dangerous_html = True
                elif attr_lower in ("href", "src"):
                    val_str = "".join(val).lower() if isinstance(val, list) else str(val).lower()
                    if val_str.startswith("javascript:") or val_str.startswith("vbscript:"):
                        report.dangerous_html = True

        # 4. Images preserved
        if len(original_soup.find_all("img")) != len(updated_soup.find_all("img")):
            report.images_preserved = False

        # 5. Tables preserved
        if len(original_soup.find_all("table")) != len(updated_soup.find_all("table")):
            report.tables_preserved = False

        # 6. Links preserved
        def get_links(soup: BeautifulSoup) -> set[str]:
            links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                links.add("".join(href).strip() if isinstance(href, list) else str(href).strip())
            return links

        if get_links(original_soup) - get_links(updated_soup):
            report.links_preserved = False

        # 7. Structure preserved (Headings, CSS, IDs, Gutenberg comments)
        def get_structure_fingerprint(soup: BeautifulSoup) -> tuple[int, set[str], set[str], int]:
            headings = len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
            classes = set()
            ids = set()
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
            
            from bs4 import Comment
            gutenberg = sum(1 for c in soup.find_all(string=lambda text: isinstance(text, Comment)) if "wp:" in str(c))
            return headings, classes, ids, gutenberg

        orig_headings, orig_classes, orig_ids, orig_gutenberg = get_structure_fingerprint(original_soup)
        upd_headings, upd_classes, upd_ids, upd_gutenberg = get_structure_fingerprint(updated_soup)

        if orig_headings != upd_headings:
            report.structure_preserved = False
        # Gutenberg: only fail if the original HAD comments and they were
        # removed or reduced.  If the original had 0, the AI adding some is
        # harmless (they get stripped in post-processing anyway).
        if orig_gutenberg > 0 and upd_gutenberg < orig_gutenberg:
            report.structure_preserved = False
        if orig_classes - upd_classes:
            report.structure_preserved = False
        if orig_ids - upd_ids:
            report.structure_preserved = False

        # 8. Statistics
        orig_words = len(original_soup.get_text().split())
        upd_words = len(updated_soup.get_text().split())
        report.word_diff = upd_words - orig_words

        orig_len = len(original_html.encode("utf-8"))
        upd_len = len(updated_html.encode("utf-8"))
        if orig_len > 0:
            report.html_diff_percent = round(((upd_len - orig_len) / orig_len) * 100, 2)
        else:
            report.html_diff_percent = 100.0

        # Overall Status
        is_valid = (
            report.html_valid
            and not report.prompt_leakage
            and not report.dangerous_html
            and report.images_preserved
            and report.links_preserved
            and report.tables_preserved
            and report.structure_preserved
        )

        if not is_valid:
            report.status = "FAIL"
            report.ready_to_publish = False

        return report
