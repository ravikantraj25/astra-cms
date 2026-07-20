"""Application logic for generating HTML from an Update Plan."""

from __future__ import annotations

import logging
import time

import httpx
from bs4 import BeautifulSoup, Tag

from app.application.prompt_builder import build_section_update_prompt
from app.domain.ai import AIProvider
from app.domain.article import Article, Section
from app.domain.plan import UpdatePlan, UpdateReport

logger = logging.getLogger(__name__)


def sanitize_html(html: str) -> str:
    """Sanitize HTML by stripping scripts, objects, and dangerous attributes."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove dangerous tags
    for tag in soup.find_all(["script", "style", "object", "embed", "applet", "iframe"]):
        # Keep trusted iframes (e.g. YouTube)
        if tag.name == "iframe":
            src = tag.get("src", "").lower()
            if "youtube" in src or "vimeo" in src:
                continue
        tag.decompose()
        
    # Remove dangerous attributes
    for tag in soup.find_all(True):
        attrs_to_remove = []
        for attr in tag.attrs:
            if attr.lower().startswith("on"):
                attrs_to_remove.append(attr)
            elif attr.lower() in ("href", "src"):
                val = str(tag[attr]).lower()
                if val.startswith("javascript:") or val.startswith("vbscript:"):
                    attrs_to_remove.append(attr)
        for attr in attrs_to_remove:
            del tag[attr]
            
    return str(soup)


def generate_updated_article(
    article: Article,
    plan: UpdatePlan,
    ai_provider: AIProvider,
) -> tuple[str, UpdateReport]:
    """Generate a new HTML document based on the Update Plan.

    Applies updates section-by-section using robust DOM replacement via 
    BeautifulSoup and data-astra-id attributes.

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
    updates_to_process: list[tuple[Section, str, str, float]] = []

    for action in plan.actions:
        matching_section = next(
            (sec for sec in article.sections if sec.name == action.section), None
        )
        if matching_section:
            updates_to_process.append(
                (matching_section, action.action, action.reason, action.confidence)
            )

    # Parse the HTML that has the data-astra-id tags
    soup = BeautifulSoup(article.raw_html, "html.parser")
    applied_confidences: list[float] = []

    for section, action_type, reason, confidence in updates_to_process:
        target_tag = soup.find(attrs={"data-astra-id": section.astra_id})
        
        if not target_tag or not isinstance(target_tag, Tag):
            logger.warning(f"Target tag for section {section.name} not found in DOM.")
            report.skipped_sections.append(section.name)
            continue

        if action_type == "Skip":
            report.skipped_sections.append(section.name)
            continue
        elif action_type == "Delete":
            # Remove the section entirely
            target_tag.decompose()
            report.updated_sections.append(section.name)
            report.section_confidences[section.name] = float(confidence)
            applied_confidences.append(confidence)
        elif action_type == "Update":
            prompt = build_section_update_prompt(section, reason)

            try:
                ai_response = ai_provider.generate(prompt)

                # Pre-clean the AI response to remove common markdown fences
                # that might have slipped inside the ASTRA markers.
                ai_response = ai_response.replace("```html", "").replace("```markdown", "").replace("```", "")

                from app.application.response_validator import validate_ai_response
                clean_html = validate_ai_response(ai_response)

                safe_html = sanitize_html(clean_html)
                new_soup = BeautifulSoup(safe_html, "html.parser")
                
                # If target_tag is not an astra-wrapper, it's a real HTML tag (like <p> or <a>).
                # We want to preserve its original attributes in case the AI stripped them.
                is_wrapper = target_tag.name == "div" and "astra-wrapper" in target_tag.get("class", [])
                
                if not is_wrapper:
                    # Find the corresponding top-level tag in the AI output
                    first_tag = next((t for t in new_soup.contents if isinstance(t, Tag)), None)
                    if first_tag and first_tag.name == target_tag.name:
                        # Restore missing classes
                        orig_classes = target_tag.get("class", [])
                        if orig_classes:
                            new_classes = first_tag.get("class", [])
                            for c in orig_classes:
                                if c not in new_classes:
                                    new_classes.append(c)
                            first_tag["class"] = new_classes
                        # Restore ID
                        if target_tag.get("id") and not first_tag.get("id"):
                            first_tag["id"] = target_tag.get("id")

                for new_tag in new_soup.contents:
                    target_tag.insert_before(new_tag)
                target_tag.decompose()

                report.updated_sections.append(section.name)
                report.section_confidences[section.name] = float(confidence)
                applied_confidences.append(confidence)
            except (ValueError, RuntimeError, httpx.HTTPError) as e:
                err_msg = f"Failed to generate update for section {section.name}: {e}"
                logger.error(err_msg)
                report.warnings.append(err_msg)
                report.skipped_sections.append(section.name)

    # Cleanup: Remove all data-astra-id attributes before returning
    for tag in soup.find_all(attrs={"data-astra-id": True}):
        del tag["data-astra-id"]
        
    # Cleanup: If we created 'astra-wrapper' divs, unwrap them
    for tag in soup.find_all("div", class_="astra-wrapper"):
        tag.unwrap()

    if applied_confidences:
        report.confidence_score = round(sum(applied_confidences) / len(applied_confidences), 2)

    report.processing_time_seconds = round(time.perf_counter() - start_time, 3)
    return str(soup), report


def generate_full_article_update(
    original_html: str,
    plan: UpdatePlan,
    ai_provider: AIProvider,
) -> tuple[str, UpdateReport]:
    """Generate an updated article using the full-article Astra CMS prompt.

    Instead of updating sections one-by-one, this sends the entire article
    HTML and the update plan in a single AI call.  The AI is instructed to
    return the complete updated HTML wrapped in ``<ASTRA_HTML_START>`` /
    ``<ASTRA_HTML_END>`` markers.

    Uses :class:`~app.application.prompt_builder.PromptBuilder` for prompt
    rendering and :func:`~app.application.response_validator.validate_ai_response`
    for strict output validation.

    Args:
        original_html: The full original HTML of the article.
        plan: The UpdatePlan specifying which sections to update.
        ai_provider: The AI provider used for generation.

    Returns:
        A tuple of ``(updated_html, report)``.

    Raises:
        RuntimeError: If the AI response fails validation (missing markers,
            banned phrases, or malformed HTML).
    """
    from app.application.prompt_builder import PromptBuilder
    from app.application.response_validator import validate_ai_response

    start_time = time.perf_counter()
    report = UpdateReport()

    if not plan.actions:
        report.processing_time_seconds = round(time.perf_counter() - start_time, 3)
        return original_html, report

    plan_json = plan.model_dump_json(indent=2)
    prompt = PromptBuilder().build(original_html, plan_json)

    ai_response = ai_provider.generate(prompt)
    updated_html = validate_ai_response(ai_response)
    updated_html = sanitize_html(updated_html)

    for action in plan.actions:
        if action.action == "Skip":
            report.skipped_sections.append(action.section)
        else:
            report.updated_sections.append(action.section)
            report.section_confidences[action.section] = float(action.confidence)

    confidences = [float(a.confidence) for a in plan.actions if a.action != "Skip"]
    if confidences:
        report.confidence_score = round(sum(confidences) / len(confidences), 2)

    report.processing_time_seconds = round(time.perf_counter() - start_time, 3)
    return updated_html, report

