"""Application logic for generating HTML from an Update Plan."""

from __future__ import annotations

import logging

from app.application.prompt_builder import build_section_update_prompt
from app.domain.ai import AIProvider
from app.domain.article import Article, Section
from app.domain.plan import UpdatePlan

logger = logging.getLogger(__name__)


def generate_updated_article(
    article: Article,
    plan: UpdatePlan,
    ai_provider: AIProvider,
) -> str:
    """Generate a new HTML document based on the Update Plan.

    Applies updates section-by-section. Uses a reverse-offset replacement
    strategy so that modifying a section's length does not invalidate the
    start and end positions of sections earlier in the document.

    Args:
        article: The parsed original Article with sections detected.
        plan: The UpdatePlan specifying which sections to update.
        ai_provider: The AI provider used for generation.

    Returns:
        The fully updated HTML string.
    """
    if not article.sections:
        return article.raw_html

    # We need to map plan actions back to the actual Section objects.
    # We create a list of (Section, action_type, reason)
    updates_to_process: list[tuple[Section, str, str]] = []

    for action in plan.actions:
        # Find the matching section
        matching_section = next(
            (sec for sec in article.sections if sec.name == action.section), None
        )
        if matching_section:
            updates_to_process.append((matching_section, action.action, action.reason))

    # Sort in descending order by start_position.
    # This ensures that replacements at the bottom of the file do not shift
    # the character offsets for replacements at the top of the file.
    updates_to_process.sort(key=lambda x: x[0].start_position, reverse=True)

    html_content = article.raw_html

    for section, action_type, reason in updates_to_process:
        if action_type == "Skip":
            continue
        elif action_type == "Delete":
            # Remove the section entirely
            html_content = (
                html_content[: section.start_position] + html_content[section.end_position :]
            )
        elif action_type == "Update":
            prompt = build_section_update_prompt(section, reason)

            try:
                ai_response = ai_provider.generate(prompt)

                # Clean up markdown blocks from response if present
                clean_html = ai_response.strip()
                if clean_html.startswith("```html"):
                    clean_html = clean_html[7:]
                elif clean_html.startswith("```"):
                    clean_html = clean_html[3:]
                if clean_html.endswith("```"):
                    clean_html = clean_html[:-3]
                clean_html = clean_html.strip()

                # Replace the old section with the new HTML
                html_content = (
                    html_content[: section.start_position]
                    + clean_html
                    + html_content[section.end_position :]
                )
            except Exception as e:
                logger.error(f"Failed to generate update for section {section.name}: {e}")
                # Fallback: leave original if generation fails
                pass

    return html_content
