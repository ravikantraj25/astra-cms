"""Prompt builder for AI-assisted article updates.

Generates structured text prompts from a parsed Article and its detected
sections.  No AI calls are made — this module only produces the prompt string.
"""

from __future__ import annotations

from app.domain.article import Article, Section


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
    lines.append("5. Optimize headings for SEO without keyword stuffing.")
    lines.append("6. Ensure each section has a clear purpose.")
    lines.append("7. Do NOT add new sections unless explicitly requested.")
    lines.append("8. Do NOT remove any existing content.")
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


def build_analysis_prompt(article: Article) -> str:
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

    lines.append("")
    lines.append("-" * 60)
    lines.append("ANALYSIS INSTRUCTIONS")
    lines.append("-" * 60)
    lines.append("")
    lines.append("Please analyze the article structure and metadata above.")
    lines.append("Provide your output EXACTLY as a valid JSON object matching this schema:")
    lines.append("{")
    lines.append('  "seo_score": 85,')
    lines.append('  "readability_score": 70,')
    lines.append('  "strengths": ["string"],')
    lines.append('  "weaknesses": ["string"],')
    lines.append('  "suggestions": ["string"]')
    lines.append("}")
    lines.append("Do NOT wrap the JSON in markdown code blocks. Return ONLY valid JSON.")

    return "\n".join(lines)


def build_section_update_prompt(section: Section, reason: str) -> str:
    """Build an AI prompt for rewriting a specific section.

    Args:
        section: The section to update.
        reason: The reason this section needs an update.

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
    lines.append("You MUST adhere strictly to the following rules:")
    lines.append("")
    lines.append("1. CRITICAL: Preserve all images (<img> tags) exactly as they are.")
    lines.append(
        "2. CRITICAL: Preserve all tables (<table>, <tr>, <td>) structure and formatting."
    )
    lines.append("3. CRITICAL: Preserve all links (<a> tags) and their exact href attributes.")
    lines.append("4. CRITICAL: Preserve all HTML schema, attributes, and classes.")
    lines.append("5. Improve clarity, grammar, and readability of the text content only.")
    lines.append("6. Maintain the original tone and intent of the article.")
    lines.append("7. Do NOT add new sections or extraneous wrapper tags (no <html>, <body>, etc).")
    lines.append("")
    lines.append("Provide your output EXACTLY as valid HTML.")
    lines.append("Do NOT wrap the HTML in markdown code blocks. Return ONLY the HTML content.")

    return "\n".join(lines)
