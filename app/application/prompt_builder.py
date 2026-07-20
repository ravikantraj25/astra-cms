"""Prompt builder for AI-assisted article updates.

Generates structured text prompts from a parsed Article and its detected
sections.  No AI calls are made — this module only produces the prompt string.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.article import Article, Section

# Path to the directory containing prompt template files.
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


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


def build_prompt(article: Article) -> str:
    """Build an AI prompt from an Article and its detected sections.

    Args:
        article: A parsed and section-detected Article.

    Returns:
        A formatted prompt string ready to be sent to an AI provider.
    """
    lines: list[str] = []

    # ── Header ───────────────────────────────────────────────────────────
    lines.append("=" * 60)
    lines.append("ARTICLE UPDATE PROMPT")
    lines.append("=" * 60)
    lines.append("")

    # ── Title ────────────────────────────────────────────────────────────
    lines.append(f"Title: {article.title or 'Untitled'}")
    lines.append(f"Article Type: {_detect_article_type(article)}")
    lines.append(f"Word Count: {article.word_count}")
    lines.append("")

    # ── Meta ─────────────────────────────────────────────────────────────
    if article.meta_description:
        lines.append(f"Meta Description: {article.meta_description}")
        lines.append("")

    # ── Sections ─────────────────────────────────────────────────────────
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

    # ── Headings ─────────────────────────────────────────────────────────
    if article.headings:
        lines.append("-" * 60)
        lines.append("HEADING STRUCTURE")
        lines.append("-" * 60)
        lines.append("")
        for heading in article.headings:
            lines.append(f"  - {heading}")
        lines.append("")

    # ── Update Instructions ──────────────────────────────────────────────
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

    # ── Output Format ────────────────────────────────────────────────────
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


def build_analysis_prompt(article: Article, custom_instructions: str | None = None) -> str:
    """Build an AI prompt for analyzing an Article.

    The generated prompt instructs the AI to return a JSON object with analysis.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("ARTICLE ANALYSIS PROMPT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Title: {article.title or 'Untitled'}")
    lines.append(f"Article Type: {_detect_article_type(article)}")
    lines.append(f"Word Count: {article.word_count}")

    if article.meta_description:
        lines.append(f"Meta Description: {article.meta_description}")

    lines.append("")
    lines.append("Here is the parsed content structure:")
    if article.headings:
        lines.append(f"Headings: {', '.join(article.headings)}")
    lines.append(f"Number of paragraphs: {len(article.paragraphs)}")
    lines.append(f"Number of images: {len(article.images)}")
    lines.append(f"Number of links: {len(article.links)}")

    if custom_instructions:
        lines.append("")
        lines.append("-" * 60)
        lines.append("CUSTOM INSTRUCTIONS FROM USER")
        lines.append("-" * 60)
        lines.append("")
        lines.append(f"CRITICAL REQUIREMENT: {custom_instructions}")
        lines.append("Ensure your analysis completely adheres to this requirement.")
        lines.append("If this requires updating dates, specify 'Update' actions for ALL sections containing dates.")

    lines.append("")
    lines.append("-" * 60)
    lines.append("ANALYSIS INSTRUCTIONS")
    lines.append("-" * 60)
    lines.append("")
    lines.append("Please analyze the article structure and metadata above.")
    lines.append("In your analysis, specifically identify:")
    lines.append(
        "1. Outdated information that needs updating (e.g., old dates, stats, deprecated tools)."
    )
    lines.append(
        "2. Evergreen content and sections that are accurate and should be preserved intact."
    )
    lines.append(
        "3. Sections that require targeted changes vs. sections where rewrites should be avoided."
    )
    lines.append(
        "4. If the title needs updating (e.g. changing the year), provide a 'new_title'. Otherwise leave it out or null."
    )
    lines.append("Provide your output EXACTLY as a valid JSON object matching this schema:")
    lines.append("{")
    lines.append('  "new_title": "string (optional new title)",')
    lines.append('  "seo_score": 85,')
    lines.append('  "readability_score": 70,')
    lines.append('  "strengths": ["string"],')
    lines.append('  "weaknesses": ["string"],')
    lines.append('  "suggestions": ["string"]')
    lines.append("}")
    lines.append("Do NOT wrap the JSON in markdown code blocks. Return ONLY valid JSON.")

    return "\n".join(lines)


def build_section_update_prompt(section: Section, reason: str, custom_instructions: str | None = None) -> str:
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
    lines.append("7. Detect and update any outdated information (dates, statistics, obsolete details).")
    lines.append("8. Preserve evergreen content and timeless definitions without modification.")
    lines.append("9. Update only what needs changes based on the reason; avoid unnecessary rewrites.")
    lines.append("10. Maintain consistent tone, voice, and formatting across the section.")
    lines.append("11. Improve clarity and readability of the text while keeping accurate parts unchanged.")
    lines.append("12. Do NOT add new sections or extraneous wrapper tags (no <html>, <body>, etc).")
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
