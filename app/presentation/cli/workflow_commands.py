"""CLI commands for orchestrating workflows."""

from __future__ import annotations

import json
from pathlib import Path

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
    instructions: str = typer.Option(
        None,
        "--instructions",
        "-i",
        help="Custom instructions for the AI (e.g. 'Update all dates to 2026').",
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
        with wp_client, console.status(f"[dim]Running analysis workflow for post {post_id}...[/dim]"):
            artifacts = run_analysis_workflow(
                post_id=post_id,
                wp_client=wp_client,
                ai_provider=ai_provider,
                output_dir=output_dir,
                custom_instructions=instructions,
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
        if settings.is_debug:
            raise err
        raise typer.Exit(code=1)


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
        if settings.is_debug:
            raise err
        raise typer.Exit(code=1)


@workflow_app.command("validate")
def validate(
    html_file: Path = typer.Argument(
        ...,
        help="The updated HTML file to validate.",
    ),
) -> None:
    """Validate generated HTML against the original post."""
    settings = get_settings()
    output_dir = settings.base_dir / OUTPUT_DIR

    if not html_file.exists():
        console.print(f"  [red]✘ File not found:[/red] [white]{html_file}[/white]")
        raise typer.Exit(code=1)

    # Infer original file path (e.g. post_123_updated.html -> post_123.html)
    original_file = html_file.parent / html_file.name.replace("_updated", "")
    if not original_file.exists():
        console.print(f"  [red]✘ Original file not found at:[/red] [white]{original_file}[/white]")
        raise typer.Exit(code=1)

    try:
        original_html = original_file.read_text(encoding="utf-8")
        updated_html = html_file.read_text(encoding="utf-8")

        from app.application.quality_validator import QualityValidator

        with console.status("[dim]Validating HTML...[/dim]"):
            report = QualityValidator.validate(original_html, updated_html)

        report_file = output_dir / "validation_report.json"
        report_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        console.print("\n[bold]Validation Report[/bold]")
        console.print("─────────────────")

        def _format_check(passed: bool, label: str) -> str:
            return f"[green]✔ {label}[/green]" if passed else f"[red]✘ {label}[/red]"

        console.print(_format_check(report.html_valid, "HTML Valid"))
        console.print(_format_check(not report.prompt_leakage, "Prompt Leakage"))
        console.print(_format_check(not report.dangerous_html, "Dangerous HTML"))
        console.print(_format_check(not report.year_mismatch, "Year Consistency"))
        console.print(_format_check(report.images_preserved, "Images Preserved"))
        console.print(_format_check(report.links_preserved, "Links Preserved"))
        console.print(_format_check(report.tables_preserved, "Tables Preserved"))
        console.print(_format_check(report.structure_preserved, "Structure Preserved"))

        console.print("─────────────────")
        if report.ready_to_publish:
            console.print("[bold green]Overall Result: PASS[/bold green]\n")
            raise typer.Exit(code=0)
        else:
            console.print("[bold red]Overall Result: FAIL[/bold red]\n")
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as err:
        console.print()
        console.print(f"  [red]✘ Validation Error:[/red] {err}")
        if settings.is_debug:
            raise err
        raise typer.Exit(code=1)


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
    original_file = output_dir / f"post_{post_id}.html"

    if not updated_file.exists():
        console.print(
            f"  [red]✘ Updated HTML file not found at[/red] [white]{updated_file}[/white]"
        )
        console.print(f"  [dim]Please run `astra workflow generate {post_id}` first.[/dim]")
        raise typer.Exit(code=1)
        
    if not original_file.exists():
        console.print(
            f"  [red]✘ Original HTML file not found at[/red] [white]{original_file}[/white]"
        )
        console.print(f"  [dim]Please run `astra workflow analyze {post_id}` first.[/dim]")
        raise typer.Exit(code=1)

    try:
        original_html = original_file.read_text(encoding="utf-8")
        updated_html = updated_file.read_text(encoding="utf-8")

        from app.application.quality_validator import QualityValidator

        with console.status("[dim]Validating HTML before publish...[/dim]"):
            report = QualityValidator.validate(original_html, updated_html)

        if not report.ready_to_publish:
            console.print("  [red]✘ Quality validation failed. Aborting publish.[/red]")
            
            def _get_failures(r) -> list[str]:
                failures = []
                if not r.html_valid: failures.append("HTML is invalid")
                if r.prompt_leakage: failures.append("Prompt leakage detected")
                if r.dangerous_html: failures.append("Dangerous HTML tags/attributes detected")
                if r.year_mismatch: failures.append("Title/body year mismatch detected")
                if not r.images_preserved: failures.append("Images were altered")
                if not r.links_preserved: failures.append("Links were altered")
                if not r.tables_preserved: failures.append("Tables were altered")
                if not r.structure_preserved: failures.append("Structure was altered")
                return failures
            
            for failure in _get_failures(report):
                console.print(f"    [red]- {failure}[/red]")
                
            console.print(f"  [dim]Check output/validation_report.json for details.[/dim]")
            raise typer.Exit(code=1)
            
        console.print("  [green]✔ Quality Validation Passed[/green]")

        wp_client = WordPressClient(
            base_url=wp_settings.base_url,
            username=wp_settings.username,
            app_password=wp_settings.app_password.get_secret_value(),
            timeout=(wp_settings.timeout_connect, wp_settings.timeout_read),
            verify_ssl=wp_settings.verify_ssl,
        )
        with wp_client:
            console.print("  [green]✔ Connected[/green]")

            content = updated_html
            console.print("  [green]✔ Loaded updated HTML[/green]")

            plan_file = output_dir / "update_plan.json"
            new_title = None
            if plan_file.exists():
                try:
                    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
                    new_title = plan_data.get("new_title")
                except Exception:
                    pass

            kwargs = {
                "post_id": post_id,
                "content": content,
                "status": "draft",
            }
            if new_title:
                kwargs["title"] = new_title
                console.print(f"  [green]✔ Loaded new title:[/green] [white]{new_title}[/white]")

            updated_post = wp_client.update_post(**kwargs)
            console.print("  [green]✔ Uploaded draft[/green]")
            console.print(f"  [green]✔ Draft URL:[/green] [cyan]{updated_post.link}[/cyan]")

    except typer.Exit:
        raise
    except Exception as err:
        console.print()
        console.print(f"  [red]✘ Publish Failed:[/red] {err}")
        if settings.is_debug:
            raise err
        raise typer.Exit(code=1)
