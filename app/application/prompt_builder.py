"""Prompt builder for AI-assisted article updates.

Generates structured text prompts from a parsed Article and its detected
sections.  No AI calls are made — this module only produces the prompt string.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString, Comment

from app.domain.article import Article, Section

# Path to the directory containing prompt template files.
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _get_current_year() -> int:
    return datetime.now().year


def _detect_article_type(article: Article) -> str:
    """Infer a human-readable article type from the article content."""
    heading_text = " ".join(h.lower() for h in article.headings)

    if any(kw in heading_text for kw in ("faq", "frequently asked")):
        return "FAQ / Knowledge-Base Article"
    if any(kw in heading_text for kw in ("schedule", "agenda", "venue", "event")):
        return "Event Page"
    if any(kw in heading_text for kw in ("tutorial", "how to", "step", "guide")):
        return "Tutorial / How-To Guide"
    if any(kw in heading_text for kw in ("review", "comparison", "vs")):
        return "Review / Comparison"
    if any(kw in heading_text for kw in ("news", "press", "announcement")):
        return "News / Press Release"
    return "General Article"


def _truncate_html(html: str, max_chars: int = 2000) -> str:
    """Truncate HTML content to fit within token limits safely.

    Walks the DOM recursively and appends complete child elements
    until the character limit is reached. Always returns valid HTML.
    """
    if len(html) <= max_chars:
        return html

    soup = BeautifulSoup(html, "html.parser")
    new_soup = BeautifulSoup("", "html.parser")
    
    current_length = 0
    
    def walk_and_truncate(node, parent_node) -> bool:
        """Returns True if the node fit completely, False if it reached the limit."""
        nonlocal current_length
        
        if current_length >= max_chars:
            return False
            
        node_html = str(node)
        if current_length + len(node_html) <= max_chars:
            # The entire node fits perfectly. Parse and append its children exactly.
            parsed_node = BeautifulSoup(node_html, "html.parser")
            parent_node.extend(list(parsed_node.children))
            current_length += len(node_html)
            return True
            
        # The node doesn't fully fit.
        if isinstance(node, Comment):
            return False
            
        if isinstance(node, NavigableString):
            allowed_len = max_chars - current_length
            if allowed_len > 0:
                truncated_text = str(node)[:allowed_len]
                parent_node.append(NavigableString(truncated_text))
                current_length += len(truncated_text)
            return False
            
        if isinstance(node, Tag):
            # The tag doesn't fully fit, try to fit its children.
            new_tag = new_soup.new_tag(node.name)
            new_tag.attrs = node.attrs.copy()
            parent_node.append(new_tag)
            
            empty_tag_len = len(str(new_tag))
            current_length += empty_tag_len
            
            if current_length >= max_chars:
                return False
                
            for child in node.children:
                if not walk_and_truncate(child, new_tag):
                    break
                    
            return False
            
        return False

    for child in soup.children:
        if not walk_and_truncate(child, new_soup):
            break
            
    truncated = str(new_soup)
    return truncated + "\n... [TRUNCATED] ..."


# ── Analysis prompt (the big redesign) ───────────────────────────────────────


def build_analysis_prompt(
    article: Article,
    custom_instructions: str | None = None,
) -> str:
    """Build a deep-inspection analysis prompt.

    Instead of sending only metadata, this prompt sends **every detected
    section's name, type, and raw HTML** so the AI can inspect the actual
    content and make per-section Update / Skip / Delete decisions.

    Args:
        article: A parsed and section-detected Article.
        custom_instructions: Optional user-supplied instructions.

    Returns:
        A formatted prompt string ready to be sent to an AI provider.
    """
    lines: list[str] = []
    current_year = _get_current_year()

    # ── Header ────────────────────────────────────────────────────────────
    lines.append("=" * 60)
    lines.append("ASTRA CMS — DEEP ARTICLE ANALYSIS")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Title: {article.title or 'Untitled'}")
    lines.append(f"Article Type: {_detect_article_type(article)}")
    lines.append(f"Word Count: {article.word_count}")
    lines.append(f"Current Year: {current_year}")
    if article.meta_description:
        lines.append(f"Meta Description: {article.meta_description}")
    lines.append("")

    # ── Custom instructions ───────────────────────────────────────────────
    if custom_instructions:
        lines.append("-" * 60)
        lines.append("CUSTOM INSTRUCTIONS FROM USER")
        lines.append("-" * 60)
        lines.append("")
        lines.append(f"CRITICAL REQUIREMENT: {custom_instructions}")
        lines.append(
            "Apply these instructions to EVERY section decision below."
        )
        lines.append("")

    # ── All sections with HTML ────────────────────────────────────────────
    lines.append("-" * 60)
    lines.append("SECTIONS TO INSPECT")
    lines.append("-" * 60)
    lines.append("")

    if article.sections:
        for idx, section in enumerate(article.sections, 1):
            lines.append(f"--- SECTION {idx} ---")
            lines.append(f"SECTION ID (astra_id): {section.astra_id}")
            lines.append(f"SECTION NAME: {section.name}")
            lines.append(f"SECTION TYPE: {section.type}")
            lines.append(f"SECTION HTML:")
            lines.append(_truncate_html(section.content))
            lines.append("")
    else:
        lines.append("No sections detected.")
        lines.append("")

    # ── Decision rules ────────────────────────────────────────────────────
    lines.append("-" * 60)
    lines.append("DECISION RULES")
    lines.append("-" * 60)
    lines.append("")
    lines.append("For EACH section above, you MUST evaluate it independently:")
    lines.append("  1. Inspect one section completely.")
    lines.append("  2. Determine if it needs to be Update / Skip / Delete.")
    lines.append("  3. Assign a confidence score (0-100).")
    lines.append("  4. Assign a priority based on the Priority Rules below.")
    lines.append("  5. Only then continue to the next section.")
    lines.append("")
    lines.append("Mark as UPDATE if the section contains:")
    lines.append(f"  - Outdated year references (anything before {current_year})")
    lines.append("  - Outdated statistics, figures, or data")
    lines.append("  - Obsolete software versions or tools")
    lines.append("  - Event schedules, dates, timings")
    lines.append("  - Registration, ticketing, or pricing info")
    lines.append("  - Muhurat, panchang, or calendar dates")
    lines.append("  - Image alt text referencing an old year")
    lines.append("  - Table cells with old dates or prices")
    lines.append("")
    lines.append("Mark as SKIP if the section contains:")
    lines.append("  - History, mythology, or cultural explanations")
    lines.append("  - Evergreen definitions or timeless FAQs")
    lines.append("  - Accurately sourced statistics that are still current")
    lines.append("  - Content that is already up to date")
    lines.append("")
    lines.append("Mark as DELETE only if:")
    lines.append("  - The section is a duplicate of another section")
    lines.append("  - The section is entirely irrelevant filler")
    lines.append("")
    lines.append("PRIORITY RULES:")
    lines.append("  HIGH: Old year, Broken links, Wrong dates, Event schedules, Registration, Pricing")
    lines.append("  MEDIUM: Outdated wording, Old statistics")
    lines.append("  LOW: Grammar, SEO, Minor clarity improvements")
    lines.append("")

    # ── Title rule ────────────────────────────────────────────────────────
    lines.append("-" * 60)
    lines.append("TITLE RULE")
    lines.append("-" * 60)
    lines.append("")
    lines.append(
        f"If the current title contains a year before {current_year}, "
        f"provide a 'new_title' with {current_year}."
    )
    lines.append("Otherwise set new_title to null.")
    lines.append("")

    # ── Output format ─────────────────────────────────────────────────────
    lines.append("-" * 60)
    lines.append("OUTPUT FORMAT — STRICT JSON")
    lines.append("-" * 60)
    lines.append("")
    lines.append("Return ONLY a valid JSON object. No markdown. No explanation.")
    lines.append("Do NOT wrap in ```json code fences.")
    lines.append("")
    lines.append("{")
    lines.append('  "new_title": "string or null",')
    lines.append('  "strengths": ["string"],')
    lines.append('  "weaknesses": ["string"],')
    lines.append('  "suggestions": ["string"],')
    lines.append('  "section_decisions": [')
    lines.append("    {")
    lines.append('      "astra_id": "exact astra_id or null",')
    lines.append('      "section": "exact section name",')
    lines.append('      "action": "Update",')
    lines.append('      "priority": "High",')
    lines.append('      "confidence": 98,')
    lines.append(f'      "reason": "Contains {current_year - 1} references that must be updated."')
    lines.append("    }")
    lines.append("  ]")
    lines.append("}")
    lines.append("")
    lines.append("IMPORTANT:")
    lines.append("- You MUST include a decision for EVERY section listed above.")
    lines.append("- section names must EXACTLY match the SECTION NAME values above.")
    lines.append(f"- The current year is {current_year}.")
    lines.append("- Do NOT add sections that were not listed.")
    lines.append("- Return ONLY the JSON object. No other text.")

    return "\n".join(lines)


# ── Legacy prompt (kept for backward compatibility) ──────────────────────────


def build_prompt(article: Article) -> str:
    """Build an AI prompt from an Article and its detected sections.

    Args:
        article: A parsed and section-detected Article.

    Returns:
        A formatted prompt string ready to be sent to an AI provider.
    """
    lines: list[str] = []

    lines.append("=" * 60)
    lines.append("ARTICLE UPDATE PROMPT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Title: {article.title or 'Untitled'}")
    lines.append(f"Article Type: {_detect_article_type(article)}")
    lines.append(f"Word Count: {article.word_count}")
    lines.append("")

    if article.meta_description:
        lines.append(f"Meta Description: {article.meta_description}")
        lines.append("")

    lines.append("-" * 60)
    lines.append("DETECTED SECTIONS")
    lines.append("-" * 60)
    lines.append("")

    if article.sections:
        for idx, section in enumerate(article.sections, 1):
            lines.append(f"  {idx}. [{section.type}] {section.name}")
    else:
        lines.append("  No sections detected.")
    lines.append("")

    if article.headings:
        lines.append("-" * 60)
        lines.append("HEADING STRUCTURE")
        lines.append("-" * 60)
        lines.append("")
        for heading in article.headings:
            lines.append(f"  - {heading}")
        lines.append("")

    lines.append("-" * 60)
    lines.append("UPDATE INSTRUCTIONS")
    lines.append("-" * 60)
    lines.append("")
    lines.append("Please rewrite and improve the article above following these rules:")
    lines.append("")
    lines.append("1. Preserve the original structure and section order.")
    lines.append("2. Improve clarity, grammar, and readability.")
    lines.append("3. Maintain the original tone and intent.")
    lines.append("4. Keep all factual information accurate.")
    lines.append(
        "5. Detect and update any outdated information (dates, stats, deprecated details)."
    )
    lines.append(
        "6. Preserve evergreen content, timeless definitions, and accurate historical facts."
    )
    lines.append("7. Update only sections that need changes; keep tone and formatting consistent.")
    lines.append(
        "8. Avoid unnecessary rewrites or stylistic churn where content is already accurate."
    )
    lines.append("9. Optimize headings for SEO without keyword stuffing.")
    lines.append("10. Ensure each section has a clear purpose.")
    lines.append("11. Do NOT add new sections unless explicitly requested.")
    lines.append("12. Do NOT remove any existing content.")
    lines.append("")

    lines.append("-" * 60)
    lines.append("OUTPUT FORMAT")
    lines.append("-" * 60)
    lines.append("")
    lines.append("Return the updated article as valid HTML.")
    lines.append("Wrap each section in appropriate HTML tags.")
    lines.append("Use semantic HTML5 elements where possible.")
    lines.append("Do NOT include <html>, <head>, or <body> tags.")
    lines.append("Return ONLY the article body content.")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


# ── Section update prompt ────────────────────────────────────────────────────


def build_section_update_prompt(
    section: Section,
    reason: str,
    custom_instructions: str | None = None,
) -> str:
    """Build an AI prompt for rewriting a specific section.

    Args:
        section: The section to update.
        reason: The reason this section needs an update.
        custom_instructions: Optional instructions to force specific updates.

    Returns:
        A formatted prompt string for generating updated section HTML.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("SECTION UPDATE PROMPT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Section Name: {section.name}")
    lines.append(f"Section Type: {section.type}")
    lines.append(f"Update Reason: {reason}")
    if custom_instructions:
        lines.append(f"Custom Instructions: {custom_instructions}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("ORIGINAL HTML")
    lines.append("-" * 60)
    lines.append("")
    lines.append(section.content)
    lines.append("")
    lines.append("-" * 60)
    lines.append("UPDATE INSTRUCTIONS")
    lines.append("-" * 60)
    lines.append("")
    lines.append("Please rewrite and improve the HTML section above based on the Update Reason.")
    if custom_instructions:
        lines.append(f"CRITICAL REQUIREMENT FROM USER: {custom_instructions}")
    lines.append("You MUST adhere strictly to the following rules:")
    lines.append("")
    lines.append("1. CRITICAL: Preserve all images (<img> tags) exactly as they are.")
    lines.append("2. CRITICAL: Preserve all tables (<table>, <tr>, <td>) structure and formatting.")
    lines.append("3. CRITICAL: Preserve all links (<a> tags) and their exact href attributes.")
    lines.append("4. CRITICAL: Preserve all HTML schema, attributes, IDs, and CSS classes exactly.")
    lines.append("5. CRITICAL: Preserve all Gutenberg comments (<!-- wp:... --> and <!-- /wp:... -->) exactly.")
    lines.append("6. CRITICAL: Preserve the exact nesting, wrappers, and structure of all elements.")
    lines.append("7. CRITICAL: Do NOT modify image src or srcset URLs.")
    lines.append("8. Detect and update any outdated information (dates, statistics, obsolete details).")
    lines.append("9. Preserve evergreen content and timeless definitions without modification.")
    lines.append("10. Update only what needs changes based on the reason; avoid unnecessary rewrites.")
    lines.append("11. Maintain consistent tone, voice, and formatting across the section.")
    lines.append("12. Improve clarity and readability of the text while keeping accurate parts unchanged.")
    lines.append("13. Do NOT add new sections or extraneous wrapper tags (no <html>, <body>, etc).")
    lines.append("")
    lines.append("Provide your output EXACTLY as valid HTML.")
    lines.append("Do NOT wrap the HTML in markdown code blocks (no ```html). Return ONLY the raw HTML.")
    lines.append("Do NOT output any conversational text, greetings, reasoning, or explanations.")
    lines.append("")
    lines.append("CRITICAL: You MUST wrap your entire HTML output between these exact markers:")
    lines.append("<ASTRA_HTML_START>")
    lines.append("... your html here ...")
    lines.append("<ASTRA_HTML_END>")

    return "\n".join(lines)


# ── Full-article update prompt (template-based) ─────────────────────────────


def build_full_article_update_prompt(
    original_html: str,
    update_plan_json: str,
) -> str:
    """Build the production Astra CMS AI Editor prompt.

    Convenience wrapper around :class:`PromptBuilder` for backward
    compatibility.  Loads the template from the ``templates/`` directory.

    Args:
        original_html: The full original HTML of the article.
        update_plan_json: The serialised update plan JSON.

    Returns:
        The complete prompt string ready to be sent to the AI provider.
    """
    return PromptBuilder().build(original_html, update_plan_json)


def extract_astra_html(ai_response: str) -> str:
    """Extract the HTML payload between ``<ASTRA_HTML_START>`` and ``<ASTRA_HTML_END>``.

    Falls back to stripping markdown code fences if the markers are absent.

    .. deprecated::
        Use :func:`app.application.response_validator.validate_ai_response`
        for strict validation in production pipelines.

    Args:
        ai_response: The raw text returned by the AI provider.

    Returns:
        The cleaned HTML string.

    Raises:
        ValueError: If the markers are found but the content between them is empty.
    """
    start_marker = "<ASTRA_HTML_START>"
    end_marker = "<ASTRA_HTML_END>"

    if start_marker in ai_response and end_marker in ai_response:
        start = ai_response.index(start_marker) + len(start_marker)
        end = ai_response.index(end_marker)
        html = ai_response[start:end].strip()
        if not html:
            raise ValueError("AI returned empty HTML between ASTRA markers.")
        return html

    # Fallback: strip markdown fences
    clean = ai_response.strip()
    if clean.startswith("```html"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()


class PromptBuilder:
    """Loads the full-update template from disk and renders it.

    The template is read once from ``templates/full_update.txt`` on
    construction.  Placeholders ``{{ORIGINAL_HTML}}`` and
    ``{{UPDATE_PLAN_JSON}}`` are substituted by :meth:`build`.
    """

    def __init__(self, template_path: Path | None = None) -> None:
        path = template_path or (_TEMPLATES_DIR / "full_update.txt")
        self._template = path.read_text(encoding="utf-8")

    def build(self, original_html: str, update_plan_json: str) -> str:
        """Return the rendered prompt with placeholders replaced."""
        return (
            self._template
            .replace("{{ORIGINAL_HTML}}", original_html)
            .replace("{{UPDATE_PLAN_JSON}}", update_plan_json)
        )
