"""Application logic for orchestrating the content analysis pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.application.parser import parse_html_string
from app.application.planner import build_update_plan
from app.application.prompt_builder import build_analysis_prompt
from app.application.section_detector import detect_sections
from app.domain.ai import AIProvider
from app.infrastructure.wordpress.client import WordPressClient

logger = logging.getLogger(__name__)

# Number of times to retry the AI call if JSON parsing fails.
_MAX_RETRIES: int = 2


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from AI output."""
    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()


def _extract_first_json_object(text: str) -> str:
    """Extract the first complete JSON object from a string.

    The AI sometimes appends extra text after the closing ``}``.  This
    function finds the matching brace pair and returns only the JSON
    portion.
    """
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # Fallback: return from first brace to end
    return text[start:]


def run_analysis_workflow(
    post_id: int,
    wp_client: WordPressClient,
    ai_provider: AIProvider,
    output_dir: Path,
    custom_instructions: str | None = None,
) -> dict[str, Path]:
    """Execute the complete content analysis pipeline.

    Connects to WordPress, fetches the post, saves the raw HTML, parses the
    HTML, detects sections, generates an AI prompt, fetches the AI analysis,
    and finally generates an Update Plan.

    All intermediate files are saved to the specified ``output_dir``.

    Args:
        post_id: The WordPress post ID.
        wp_client: An authenticated WordPressClient.
        ai_provider: An AI provider for text generation.
        output_dir: The directory to save all output files.
        custom_instructions: Optional instructions to inject into the prompt.

    Returns:
        A dictionary mapping the generated artifact names to their file Paths.

    Raises:
        Exception: Bubbles up any failure from the underlying services.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}

    # 1. Fetch post
    post = wp_client.get_post(post_id).post

    # 2. Save raw HTML
    html_path = output_dir / "original.html"
    html_path.write_text(post.content_html, encoding="utf-8")
    artifacts["html"] = html_path

    # Also save as post_{id}.html for the generate command
    post_html_path = output_dir / f"post_{post_id}.html"
    post_html_path.write_text(post.content_html, encoding="utf-8")

    # 3. Parse and detect sections
    article = parse_html_string(post.content_html)
    article = detect_sections(article)

    # 4. Save article.json
    article_path = output_dir / "article.json"
    article_path.write_text(article.model_dump_json(indent=2), encoding="utf-8")
    artifacts["article"] = article_path

    # 5. Generate prompt and save
    prompt = build_analysis_prompt(article, custom_instructions=custom_instructions)
    prompt_path = output_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    artifacts["prompt"] = prompt_path

    # 6. Generate AI response (with retries for JSON validity)
    analysis_result = None

    for attempt in range(_MAX_RETRIES + 1):
        response_text = ai_provider.generate(prompt)

        clean_text = _strip_markdown_fences(response_text)
        clean_text = _extract_first_json_object(clean_text)

        try:
            analysis_data = json.loads(clean_text)
            from app.domain.plan import AnalysisResult

            analysis_result = AnalysisResult.model_validate(analysis_data)
            break
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                f"Failed to parse AI output as JSON (attempt {attempt + 1}): {e}"
            )
            logger.warning(f"Raw AI response:\n{response_text}")
            if attempt == _MAX_RETRIES:
                raise ValueError(
                    f"AI failed to return valid JSON after {_MAX_RETRIES + 1} attempts.\n"
                    f"Raw Response: {response_text}"
                ) from e

    # 7. Save analysis.json
    analysis_path = output_dir / "analysis.json"
    analysis_path.write_text(
        analysis_result.model_dump_json(indent=2), encoding="utf-8"
    )
    artifacts["analysis"] = analysis_path

    # 8. Build update plan
    plan = build_update_plan(
        article, analysis_result, custom_instructions=custom_instructions
    )

    # 9. Save update_plan.json
    plan_path = output_dir / "update_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    artifacts["plan"] = plan_path

    return artifacts
