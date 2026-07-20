"""Application logic for orchestrating the content analysis pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from app.application.parser import parse_html_string
from app.application.planner import build_update_plan
from app.application.prompt_builder import build_analysis_prompt
from app.application.section_detector import detect_sections
from app.domain.ai import AIProvider
from app.infrastructure.wordpress.client import WordPressClient


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

    All intermediate files are saved to the specified `output_dir`.

    Args:
        post_id: The WordPress post ID.
        wp_client: An authenticated WordPressClient.
        ai_provider: An AI provider for text generation.
        output_dir: The directory to save all output files.

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

    import logging
    logger = logging.getLogger(__name__)
    
    # 6. Generate AI response (with 1 retry for JSON validity)
    max_retries = 1
    analysis_data = None
    analysis_result = None

    for attempt in range(max_retries + 1):
        response_text = ai_provider.generate(prompt)

        # Clean markdown
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            analysis_data = json.loads(clean_text)
            from app.domain.plan import AnalysisResult
            analysis_result = AnalysisResult.model_validate(analysis_data)
            break
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse AI output as JSON (attempt {attempt + 1}): {e}")
            logger.warning(f"Raw AI response:\n{response_text}")
            if attempt == max_retries:
                raise ValueError(f"AI failed to return valid JSON after {max_retries + 1} attempts.\nRaw Response: {response_text}") from e

    # 7. Save analysis.json
    analysis_path = output_dir / "analysis.json"
    analysis_path.write_text(analysis_result.model_dump_json(indent=2), encoding="utf-8")
    artifacts["analysis"] = analysis_path

    # 8. Build update plan
    plan = build_update_plan(article, analysis_result, custom_instructions=custom_instructions)

    # 9. Save update_plan.json
    plan_path = output_dir / "update_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    artifacts["plan"] = plan_path

    return artifacts
