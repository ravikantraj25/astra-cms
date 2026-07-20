"""Application logic for generating HTML from an Update Plan.

Only sections marked ``Update`` are rewritten by the AI.  Sections marked
``Skip`` are left untouched; sections marked ``Delete`` are removed.
"""

from __future__ import annotations

import logging
import time

import httpx
from bs4 import BeautifulSoup, Tag

from app.application.prompt_builder import build_section_update_prompt, PromptBuilder
from app.application.response_validator import validate_ai_response
from app.domain.ai import AIProvider
from app.domain.article import Article, Section
from app.domain.plan import UpdatePlan, UpdateReport, ActionType, SectionDecision

logger = logging.getLogger(__name__)

# Minimum confidence threshold for updating a section
_MIN_CONFIDENCE = 0.70


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


def _record_action(
    report: UpdateReport,
    section_name: str,
    action_type: ActionType,
    confidence: float,
    applied_confidences: list[float] | None = None,
) -> None:
    """Helper to record the outcome of a section action in the report."""
    if action_type == ActionType.SKIP:
        report.skipped_sections.append(section_name)
    else:
        report.updated_sections.append(section_name)
        report.section_confidences[section_name] = float(confidence)
        if applied_confidences is not None:
            applied_confidences.append(float(confidence))


def _finalize_report(report: UpdateReport, start_time: float, applied_confidences: list[float] | None = None) -> None:
    """Calculate aggregate scores and set processing time."""
    if applied_confidences is None:
        applied_confidences = [float(conf) for conf in report.section_confidences.values()]
        
    if applied_confidences:
        report.confidence_score = round(sum(applied_confidences) / len(applied_confidences), 2)

    report.processing_time_seconds = round(time.perf_counter() - start_time, 3)


def generate_updated_article(
    article: Article,
    plan: UpdatePlan,
    ai_provider: AIProvider,
) -> tuple[str, UpdateReport]:
    """Generate a new HTML document based on the Update Plan.

    Only sections with ``action == ActionType.UPDATE`` are sent to the AI for
    rewriting.  Sections marked ``ActionType.SKIP`` are left untouched.  Sections
    marked ``ActionType.DELETE`` are removed from the DOM.

    Args:
        article: The parsed original Article with sections detected.
        plan: The UpdatePlan specifying which sections to update.
        ai_provider: The AI provider used for generation.

    Returns:
        A tuple of ``(updated_html, report)``.
    """
    start_time = time.perf_counter()
    report = UpdateReport()

    if not article.sections:
        _finalize_report(report, start_time, [])
        return article.raw_html, report

    # Map plan actions by astra_id AND name (for fallback)
    action_map_by_id: dict[str, SectionDecision] = {}
    action_map_by_name: dict[str, SectionDecision] = {}
    
    for act in plan.actions:
        if act.section_id:
            action_map_by_id[act.section_id] = act
        action_map_by_name[act.section] = act

    # Parse the HTML that has the data-astra-id tags
    soup = BeautifulSoup(article.raw_html, "html.parser")
    applied_confidences: list[float] = []

    for section in article.sections:
        # Prefer astra_id match, fallback to name match
        decision = action_map_by_id.get(section.astra_id)
        if not decision:
            decision = action_map_by_name.get(section.name)
            
        if not decision:
            logger.warning("No plan decision found for section %s.", section.name)
            report.skipped_sections.append(section.name)
            continue

        target_tag = soup.find(attrs={"data-astra-id": section.astra_id})

        if not target_tag or not isinstance(target_tag, Tag):
            logger.warning("Target tag for section %s not found in DOM.", section.name)
            report.skipped_sections.append(section.name)
            continue

        action_type = decision.action
        confidence = decision.confidence

        # ── Low Confidence Abort ──────────────────────────────────────
        if action_type == ActionType.UPDATE and confidence < _MIN_CONFIDENCE:
            msg = f"Aborted update due to low confidence ({confidence} < {_MIN_CONFIDENCE})"
            logger.warning("Skipping section %s: %s", section.name, msg)
            report.skipped_sections.append(section.name)
            report.diagnostics[section.name] = msg
            continue

        # ── Skip: leave untouched ─────────────────────────────────────
        if action_type == ActionType.SKIP:
            _record_action(report, section.name, action_type, confidence)
            continue

        # ── Delete: remove from DOM ───────────────────────────────────
        if action_type == ActionType.DELETE:
            target_tag.decompose()
            _record_action(report, section.name, action_type, confidence, applied_confidences)
            continue

        # ── Update: rewrite via AI with Retry Loop ────────────────────
        custom_instr = plan.custom_instructions
        
        MAX_RETRIES = 2
        safe_html = section.content # Fallback to original
        is_success = False
        
        from app.application.section_validator import SectionValidator
        
        for attempt in range(MAX_RETRIES + 1):
            prompt = build_section_update_prompt(section, decision, custom_instr)
            
            if attempt > 0:
                prompt += "\n\nCRITICAL: Validation Failed on your previous attempt!\n"
                prompt += "You violated the following strict rules:\n"
                for rule in failed_rules:
                    prompt += f"- {rule}\n"
                prompt += "\nPlease fix these errors and regenerate the HTML exactly according to the rules."
                
            try:
                ai_response = ai_provider.generate(prompt)
                clean_html = validate_ai_response(ai_response)
                
                # Run section validation
                val_result = SectionValidator.validate(section.content, clean_html, decision)
                
                if val_result.is_valid:
                    safe_html = sanitize_html(clean_html)
                    is_success = True
                    break
                else:
                    failed_rules = val_result.failed_rules
                    logger.warning(f"Validation failed for section {section.name} (Attempt {attempt+1}): {failed_rules}")
                    if attempt == MAX_RETRIES:
                        report.warnings.append(f"Validation failed after {MAX_RETRIES} retries for section {section.name}: {failed_rules}")
                        report.diagnostics[section.name] = f"Validation failed: {failed_rules}"

            except (ValueError, RuntimeError, httpx.HTTPError) as e:
                logger.error("Failed to generate update for section %s: %s", section.name, e)
                if attempt == MAX_RETRIES:
                    report.warnings.append(f"Failed to generate update for section {section.name}: {e}")
                    report.diagnostics[section.name] = f"Error during generation: {e}"
        
        if not is_success:
            # If we exhausted retries, we fallback to original and record a skip
            report.skipped_sections.append(section.name)
            continue
            
        new_soup = BeautifulSoup(safe_html, "html.parser")

        # Preserve original attributes the AI may have stripped
        is_wrapper = (
            target_tag.name == "div"
            and "astra-wrapper" in target_tag.get("class", [])
        )

        if not is_wrapper:
            first_tag = next(
                (t for t in new_soup.contents if isinstance(t, Tag)),
                None,
            )
            if first_tag and first_tag.name == target_tag.name:
                _restore_attributes(target_tag, first_tag)

        for new_tag in new_soup.contents:
            target_tag.insert_before(new_tag)
        target_tag.decompose()

        _record_action(report, section.name, action_type, confidence, applied_confidences)

    # ── Cleanup ───────────────────────────────────────────────────────────
    for tag in soup.find_all(attrs={"data-astra-id": True}):
        del tag["data-astra-id"]

    for tag in soup.find_all("div", class_="astra-wrapper"):
        tag.unwrap()

    _finalize_report(report, start_time, applied_confidences)
    return str(soup), report


def _restore_attributes(original: Tag, replacement: Tag) -> None:
    """Restore safe attributes from the original tag onto the replacement.

    The AI sometimes strips ``class``, ``id``, or other semantic attributes.
    This function copies them back from the original element, taking care
    not to overwrite explicitly modified safe attributes, and appending to class.
    """
    # Merge classes
    orig_classes = original.get("class", [])
    if orig_classes:
        new_classes = replacement.get("class", [])
        if isinstance(new_classes, str):
            new_classes = new_classes.split()
            
        for cls in orig_classes:
            if cls not in new_classes:
                new_classes.append(cls)
        replacement["class"] = new_classes

    # Restore safe attributes if missing
    safe_attrs = ["id", "role", "loading", "decoding", "alt", "title"]
    for attr in safe_attrs:
        if original.get(attr) and not replacement.get(attr):
            replacement[attr] = original.get(attr)

    # Restore data-* and aria-* attributes if missing
    for attr, orig_val in original.attrs.items():
        if (attr.startswith("data-") or attr.startswith("aria-")) and not replacement.get(attr):
            replacement[attr] = orig_val


# ── Full-article update (legacy) ─────────────────────────────────────────────


def generate_full_article_update(
    original_html: str,
    plan: UpdatePlan,
    ai_provider: AIProvider,
) -> tuple[str, UpdateReport]:
    """Generate an updated article using the full-article Astra CMS prompt.

    Instead of updating sections one-by-one, this sends the entire article
    HTML and the update plan in a single AI call.

    Args:
        original_html: The full original HTML of the article.
        plan: The UpdatePlan specifying which sections to update.
        ai_provider: The AI provider used for generation.

    Returns:
        A tuple of ``(updated_html, report)``.

    Raises:
        RuntimeError: If the AI response fails validation.
    """
    start_time = time.perf_counter()
    report = UpdateReport()

    if not plan.actions:
        _finalize_report(report, start_time, [])
        return original_html, report

    plan_json = plan.model_dump_json(indent=2)
    prompt = PromptBuilder().build(original_html, plan_json)

    ai_response = ai_provider.generate(prompt)
    updated_html = validate_ai_response(ai_response)
    updated_html = sanitize_html(updated_html)

    for action in plan.actions:
        _record_action(report, action.section, action.action, float(action.confidence))

    _finalize_report(report, start_time)
    return updated_html, report
