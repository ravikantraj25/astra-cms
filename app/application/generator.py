"""Application logic for generating HTML from an Update Plan."""

from __future__ import annotations

import logging
import time

import httpx

from app.application.prompt_builder import build_section_update_prompt
from app.domain.ai import AIProvider
from app.domain.article import Article, Section
from app.domain.plan import UpdatePlan, UpdateReport

logger = logging.getLogger(__name__)


def generate_updated_article(
    article: Article,
    plan: UpdatePlan,
    ai_provider: AIProvider,
) -> tuple[str, UpdateReport]:
    """Generate a new HTML document based on the Update Plan.

    Applies updates section-by-section. Uses a reverse-offset replacement
    strategy so that modifying a section's length does not invalidate the
    start and end positions of sections earlier in the document.

    Args:
        article: The parsed original Article with sections detected.
        plan: The UpdatePlan specifying which sections to update.
        ai_provider: The AI provider used for generation.

    Returns:
        A tuple of `(updated_html, report)` containing the updated string and
        processing telemetry.
    """
    start_time = time.perf_counter()
    report = UpdateReport()

    if not article.sections:
        report.processing_time_seconds = time.perf_counter() - start_time
        return article.raw_html, report

    # We need to map plan actions back to the actual Section objects along with confidence
    # We create a list of (Section, action_type, reason, confidence)
    updates_to_process: list[tuple[Section, str, str, float]] = []

    for action in plan.actions:
        matching_section = next(
            (sec for sec in article.sections if sec.name == action.section), None
        )
        if matching_section:
            updates_to_process.append(
                (matching_section, action.action, action.reason, action.confidence)
            )

    # Sort in descending order by start_position.
    updates_to_process.sort(key=lambda x: x[0].start_position, reverse=True)

    html_content = article.raw_html
    applied_confidences: list[float] = []

    for section, action_type, reason, confidence in updates_to_process:
        if action_type == "Skip":
            report.skipped_sections.append(section.name)
            continue
        elif action_type == "Delete":
            # Remove the section entirely
            html_content = (
                html_content[: section.start_position] + html_content[section.end_position :]
            )
            report.updated_sections.append(section.name)
            report.section_confidences[section.name] = float(confidence)
            applied_confidences.append(confidence)
        elif action_type == "Update":
            prompt = build_section_update_prompt(section, reason)

            try:
                ai_response = ai_provider.generate(prompt)

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
                report.updated_sections.append(section.name)
                report.section_confidences[section.name] = float(confidence)
                applied_confidences.append(confidence)
            except (ValueError, RuntimeError, httpx.HTTPError) as e:
                err_msg = f"Failed to generate update for section {section.name}: {e}"
                logger.error(err_msg)
                report.warnings.append(err_msg)
                report.skipped_sections.append(section.name)

    if applied_confidences:
        report.confidence_score = round(sum(applied_confidences) / len(applied_confidences), 2)

    report.processing_time_seconds = round(time.perf_counter() - start_time, 3)
    return html_content, report
