"""CLI commands for orchestrating workflows."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel

from app.application.generator import generate_updated_article
from app.application.parser import parse_html_file
from app.application.section_detector import detect_sections
from app.application.workflow import run_analysis_workflow
from app.domain.plan import UpdatePlan
from app.infrastructure.config.settings import get_groq_settings, get_settings, get_wp_settings
from app.infrastructure.providers.groq_provider import GroqProvider
from app.infrastructure.wordpress.client import WordPressClient
from app.shared.constants import APP_NAME, OUTPUT_DIR

workflow_app = typer.Typer(
    name="workflow",
    help="Execute complete orchestrated workflows.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@workflow_app.command("analyze")
def analyze(
    post_id: int = typer.Argument(
        ...,
        help="The WordPress post ID to run through the workflow.",
    ),
) -> None:
    """Run the complete content analysis pipeline for a WordPress post.

    Connects to WordPress, fetches the post, detects sections, generates an AI
    prompt, analyzes the content, and outputs an Update Plan.
    """
    settings = get_settings()
    wp_settings = get_wp_settings()
    groq_settings = get_groq_settings()

    if not wp_settings.is_configured:
        console.print("  [red]✘ WordPress credentials are not configured.[/red]")
        console.print("  [dim]Please set WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD.[/dim]")
        raise typer.Exit(code=1)

    if not groq_settings.is_configured:
        console.print("  [red]✘ Groq API credentials are not configured.[/red]")
        console.print("  [dim]Please set GROQ_API_KEY in your .env file.[/dim]")
        raise typer.Exit(code=1)

    console.print()
    console.print(f"  [dim]Executing analysis workflow for Post ID:[/dim] [cyan]{post_id}[/cyan]")
    console.print()

    wp_client = WordPressClient(
        base_url=wp_settings.base_url,
        username=wp_settings.username,
        app_password=wp_settings.app_password.get_secret_value(),
        timeout=(wp_settings.timeout_connect, wp_settings.timeout_read),
        verify_ssl=wp_settings.verify_ssl,
    )
    ai_provider = GroqProvider(groq_settings)
    output_dir = settings.base_dir / OUTPUT_DIR

    try:
        with console.status(f"[dim]Running analysis workflow for post {post_id}...[/dim]"):
            artifacts = run_analysis_workflow(
                post_id=post_id,
                wp_client=wp_client,
                ai_provider=ai_provider,
                output_dir=output_dir,
            )

        console.print("  [green]✔ Workflow Finished![/green]")
        console.print()

        for name, path in artifacts.items():
            console.print(
                f"  [magenta]{name.capitalize():<12}[/magenta] "
                f"[dim]saved to[/dim] [white]{path}[/white]"
            )

        console.print()
        console.print(
            Panel(
                f"[dim]Next step: review[/dim] [cyan]update_plan.json[/cyan] [dim]and run:[/dim]\n"
                f"[bold white]astra workflow generate {post_id}[/bold white]",
                title=f"[bold]{APP_NAME}[/bold] — Success",
                border_style="green",
                padding=(1, 2),
            )
        )

    except Exception as err:
        console.print()
        console.print(f"  [red]✘ Workflow Failed:[/red] {err}")
        raise typer.Exit(code=1) from err


@workflow_app.command("generate")
def generate(
    post_id: int = typer.Argument(
        ...,
        help="The WordPress post ID to generate updated HTML for.",
    ),
) -> None:
    """Generate updated HTML from an existing Update Plan."""
    settings = get_settings()
    groq_settings = get_groq_settings()

    if not groq_settings.is_configured:
        console.print("  [red]✘ Groq API credentials are not configured.[/red]")
        console.print("  [dim]Please set GROQ_API_KEY in your .env file.[/dim]")
        raise typer.Exit(code=1)

    output_dir = settings.base_dir / OUTPUT_DIR
    article_path = output_dir / f"post_{post_id}.html"
    plan_path = output_dir / "update_plan.json"

    if not article_path.exists():
        console.print(
            f"  [red]✘ Original article not found at[/red] [white]{article_path}[/white]"
        )
        console.print(f"  [dim]Please run `astra workflow analyze {post_id}` first.[/dim]")
        raise typer.Exit(code=1)

    if not plan_path.exists():
        console.print(f"  [red]✘ Update plan not found at[/red] [white]{plan_path}[/white]")
        console.print(f"  [dim]Please run `astra workflow analyze {post_id}` first.[/dim]")
        raise typer.Exit(code=1)

    try:
        console.print("  [green]✔ Loaded original article[/green]")
        article = parse_html_file(article_path)
        article = detect_sections(article)

        console.print("  [green]✔ Loaded AI analysis[/green]")
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        plan = UpdatePlan.model_validate(plan_data)

        console.print("  [green]✔ Applied update plan[/green]")
        provider = GroqProvider(groq_settings)
        updated_html, report = generate_updated_article(article, plan, provider)

        output_file = output_dir / f"post_{post_id}_updated.html"
        output_file.write_text(updated_html, encoding="utf-8")
        console.print("  [green]✔ Generated updated HTML[/green]")

        report_file = output_dir / "update_report.json"
        report_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print("  [green]✔ Saved update report[/green]")

    except Exception as err:
        console.print()
        console.print(f"  [red]✘ Generation Failed:[/red] {err}")
        raise typer.Exit(code=1) from err


@workflow_app.command("publish")
def publish(
    post_id: int = typer.Argument(
        ...,
        help="The WordPress post ID to publish the updated HTML to as a draft.",
    ),
) -> None:
    """Upload updated HTML to WordPress as a draft for manual review."""
    settings = get_settings()
    wp_settings = get_wp_settings()

    if not wp_settings.is_configured:
        console.print("  [red]✘ WordPress credentials are not configured.[/red]")
        console.print("  [dim]Please set WP_BASE_URL, WP_USERNAME, WP_APP_PASSWORD.[/dim]")
        raise typer.Exit(code=1)

    output_dir = settings.base_dir / OUTPUT_DIR
    updated_file = output_dir / f"post_{post_id}_updated.html"

    if not updated_file.exists():
        console.print(
            f"  [red]✘ Updated HTML file not found at[/red] [white]{updated_file}[/white]"
        )
        console.print(f"  [dim]Please run `astra workflow generate {post_id}` first.[/dim]")
        raise typer.Exit(code=1)

    try:
        wp_client = WordPressClient(
            base_url=wp_settings.base_url,
            username=wp_settings.username,
            app_password=wp_settings.app_password.get_secret_value(),
            timeout=(wp_settings.timeout_connect, wp_settings.timeout_read),
            verify_ssl=wp_settings.verify_ssl,
        )
        with wp_client:
            console.print("  [green]✔ Connected[/green]")

            content = updated_file.read_text(encoding="utf-8")
            console.print("  [green]✔ Loaded updated HTML[/green]")

            updated_post = wp_client.update_post(
                post_id=post_id,
                content=content,
                status="draft",
            )
            console.print("  [green]✔ Uploaded draft[/green]")
            console.print(f"  [green]✔ Draft URL:[/green] [cyan]{updated_post.link}[/cyan]")

    except Exception as err:
        console.print()
        console.print(f"  [red]✘ Publish Failed:[/red] {err}")
        raise typer.Exit(code=1) from err
