"""Application logic for batch processing multiple WordPress posts."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from app.application.generator import generate_updated_article
from app.application.parser import parse_html_file
from app.application.section_detector import detect_sections
from app.application.workflow import run_analysis_workflow
from app.domain.ai import AIProvider
from app.domain.batch import BatchSummaryReport, PostBatchResult
from app.domain.plan import UpdatePlan
from app.infrastructure.wordpress.client import WordPressClient
from app.infrastructure.wordpress.models import WPPost

logger = logging.getLogger(__name__)


def run_batch_workflow(
    wp_client: WordPressClient,
    ai_provider: AIProvider,
    output_dir: Path,
    status_filter: str = "publish",
    category_filter: str | None = None,
    tag_filter: str | None = None,
    limit: int | None = 10,
    dry_run: bool = False,
    on_progress: Callable[[int, str], None] | None = None,
) -> BatchSummaryReport:
    """Execute the complete update workflow across multiple WordPress posts.

    Fetches candidate posts matching the status filter, applies taxonomy
    filtering (category/tag) and limits, then processes each post through the
    analysis, generation, and draft publishing steps.

    If an error occurs on a single post, it is recorded in the report and
    processing continues for remaining posts.

    Args:
        wp_client: Authenticated WordPressClient.
        ai_provider: Configured AIProvider.
        output_dir: Base output directory for intermediate files and summary.
        status_filter: Post status to retrieve from WordPress.
        category_filter: Optional category name filter (case-insensitive).
        tag_filter: Optional tag name filter (case-insensitive).
        limit: Maximum number of posts to process across all pages.
        dry_run: If True, performs local analysis and generation but skips
            publishing drafts to WordPress.
        on_progress: Optional callback function invoked as `on_progress(post_id, message)`.

    Returns:
        A `BatchSummaryReport` with counts and detailed post outcomes.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report = BatchSummaryReport()

    candidates: list[WPPost] = []
    page = 1
    per_page = 10 if (limit is not None and limit <= 10) else 20

    with wp_client:
        while True:
            try:
                post_list = wp_client.get_posts(
                    per_page=per_page,
                    page=page,
                    status=status_filter,
                )
            except Exception as err:
                logger.error(f"Failed to retrieve candidate posts on page {page}: {err}")
                break

            if not post_list.posts:
                break

            for post in post_list.posts:
                if category_filter or tag_filter:
                    try:
                        detail = wp_client.get_post(post.id)
                        if category_filter and not any(
                            category_filter.lower() == c.lower() for c in detail.categories
                        ):
                            report.results.append(
                                PostBatchResult(
                                    post_id=post.id,
                                    title=post.title,
                                    status="skipped",
                                    error_message=f"Category mismatch ('{category_filter}')",
                                )
                            )
                            report.skipped += 1
                            continue
                        if tag_filter and not any(
                            tag_filter.lower() == t.lower() for t in detail.tags
                        ):
                            report.results.append(
                                PostBatchResult(
                                    post_id=post.id,
                                    title=post.title,
                                    status="skipped",
                                    error_message=f"Tag mismatch ('{tag_filter}')",
                                )
                            )
                            report.skipped += 1
                            continue
                    except Exception as err:
                        logger.warning(f"Could not inspect taxonomy for post {post.id}: {err}")
                        report.results.append(
                            PostBatchResult(
                                post_id=post.id,
                                title=post.title,
                                status="skipped",
                                error_message=f"Failed taxonomy check: {err}",
                            )
                        )
                        report.skipped += 1
                        continue

                candidates.append(post)
                if limit is not None and len(candidates) >= limit:
                    break

            if (limit is not None and len(candidates) >= limit) or page >= post_list.total_pages:
                break
            page += 1

        report.total_posts = len(candidates) + report.skipped

        for post in candidates:
            if on_progress:
                on_progress(post.id, f"Processing post #{post.id} ({post.title})...")

            result = PostBatchResult(post_id=post.id, title=post.title)

            try:
                if on_progress:
                    on_progress(post.id, f"Analyzing post #{post.id} with AI...")
                artifacts = run_analysis_workflow(
                    post_id=post.id,
                    wp_client=wp_client,
                    ai_provider=ai_provider,
                    output_dir=output_dir,
                )

                if on_progress:
                    on_progress(post.id, f"Generating updated HTML for post #{post.id}...")
                article = parse_html_file(artifacts["html"])
                article = detect_sections(article)
                plan_data = json.loads(artifacts["plan"].read_text(encoding="utf-8"))
                plan = UpdatePlan.model_validate(plan_data)

                updated_html, _ = generate_updated_article(article, plan, ai_provider)
                updated_file = output_dir / f"post_{post.id}_updated.html"
                updated_file.write_text(updated_html, encoding="utf-8")

                if dry_run:
                    result.status = "success"
                    result.draft_url = "N/A (dry-run)"
                    report.successful += 1
                else:
                    if on_progress:
                        on_progress(post.id, f"Publishing draft for post #{post.id}...")
                    updated_post = wp_client.update_post(
                        post_id=post.id,
                        content=updated_html,
                        status="draft",
                    )
                    result.status = "success"
                    result.draft_url = updated_post.link
                    report.draft_urls.append(updated_post.link)
                    report.successful += 1

            except Exception as err:
                logger.error(f"Failed processing post #{post.id}: {err}")
                result.status = "failed"
                result.error_message = str(err)
                report.failed += 1

            report.results.append(result)

    summary_file = output_dir / "batch_summary_report.json"
    summary_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report
