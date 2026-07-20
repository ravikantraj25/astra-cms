"""Application logic for orchestrating the content analysis pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from app.application.parser import parse_html_string
from app.application.planner import Planner
from app.application.content_intelligence import ContentIntelligenceAnalyzer
from app.application.section_detector import detect_sections
from app.domain.ai import AIProvider
from app.infrastructure.wordpress.client import WordPressClient

logger = logging.getLogger(__name__)


def run_analysis_workflow(
    post_id: int,
    wp_client: WordPressClient,
    ai_provider: AIProvider,
    output_dir: Path,
    custom_instructions: str | None = None,
) -> dict[str, Path]:
    """Execute the complete content analysis pipeline.

    Connects to WordPress, fetches the post, saves the raw HTML, parses the
    HTML, detects sections, runs Content Intelligence, and generates an Update Plan.

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

    # 5. Run Content Intelligence
    logger.info("Running Content Intelligence layer...")
    intelligence_analyzer = ContentIntelligenceAnalyzer(ai_provider)
    intelligence = intelligence_analyzer.analyze(article)
    
    intel_path = output_dir / "intelligence.json"
    intel_path.write_text(intelligence.model_dump_json(indent=2), encoding="utf-8")
    artifacts["intelligence"] = intel_path

    # 6. Build Update Plan
    logger.info("Building prescriptive Update Plan...")
    planner = Planner(ai_provider)
    plan = planner.build_plan(
        article, 
        intelligence, 
        custom_instructions=custom_instructions
    )

    # 7. Save update_plan.json
    plan_path = output_dir / "update_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    artifacts["plan"] = plan_path

    return artifacts
