"""CLI commands for automated batch processing."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.application.batch_workflow import run_batch_workflow
from app.infrastructure.config.settings import get_groq_settings, get_settings, get_wp_settings
from app.infrastructure.providers.groq_provider import GroqProvider
from app.infrastructure.wordpress.client import WordPressClient
from app.shared.constants import APP_NAME, OUTPUT_DIR

auto_app = typer.Typer(
    name="auto",
    help="Automated batch processing operations.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@auto_app.command("update")
def auto_update(
    all_posts: bool = typer.Option(
        False,
        "--all",
        help="Process all available posts matching criteria without a default limit.",
    ),
    category: str | None = typer.Option(
        None,
        "--category",
        help="Filter posts by category display name (case-insensitive).",
    ),
    tag: str | None = typer.Option(
        None,
        "--tag",
        help="Filter posts by tag display name (case-insensitive).",
    ),
    status: str = typer.Option(
        "publish",
        "--status",
        help="Post status filter to retrieve from WordPress.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of posts to process.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Perform local analysis and generation without publishing drafts to WordPress.",
    ),
) -> None:
    """Batch process multiple WordPress posts through the AI update pipeline."""
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

    # Determine effective limit
    effective_limit = limit if limit is not None else (None if all_posts else 10)

    console.print()
    mode_text = "[yellow]DRY RUN[/yellow]" if dry_run else "[cyan]PUBLISH DRAFTS[/cyan]"
    console.print(f"  [bold]Starting Batch Update ({mode_text})[/bold]")
    console.print(f"  [dim]Status filter:[/dim] [white]{status}[/white]")
    if category:
        console.print(f"  [dim]Category filter:[/dim] [white]{category}[/white]")
    if tag:
        console.print(f"  [dim]Tag filter:[/dim] [white]{tag}[/white]")
    limit_text = str(effective_limit) if effective_limit is not None else "All"
    console.print(f"  [dim]Limit:[/dim] [white]{limit_text}[/white]")
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
        with console.status(
            "[dim]Connecting and discovering candidate posts...[/dim]"
        ) as status_indicator:

            def on_progress(post_id: int, message: str) -> None:
                status_indicator.update(f"[dim]{message}[/dim]")

            report = run_batch_workflow(
                wp_client=wp_client,
                ai_provider=ai_provider,
                output_dir=output_dir,
                status_filter=status,
                category_filter=category,
                tag_filter=tag,
                limit=effective_limit,
                dry_run=dry_run,
                on_progress=on_progress,
            )

        console.print("  [green]✔ Batch Processing Finished![/green]")
        console.print()

        table = Table(show_header=False, padding=(0, 2), box=None)
        table.add_column("Metric", style="bold magenta", min_width=16)
        table.add_column("Value", style="white")

        table.add_row("Total Candidates", str(report.total_posts))
        table.add_row("Successful", f"[green]{report.successful}[/green]")
        table.add_row("Failed", f"[red]{report.failed}[/red]" if report.failed else "0")
        table.add_row("Skipped", f"[yellow]{report.skipped}[/yellow]" if report.skipped else "0")
        console.print(table)
        console.print()

        if report.draft_urls:
            console.print("  [bold cyan]Generated Draft URLs:[/bold cyan]")
            for url in report.draft_urls:
                console.print(f"  • [white]{url}[/white]")
            console.print()

        summary_file = output_dir / "batch_summary_report.json"
        console.print(
            Panel(
                f"[dim]Full summary report saved to:[/dim] [white]{summary_file}[/white]",
                title=f"[bold]{APP_NAME}[/bold] — Batch Summary",
                border_style="green",
                padding=(1, 2),
            )
        )

    except Exception as err:
        console.print()
        console.print(f"  [red]✘ Batch Processing Failed:[/red] {err}")
        if settings.is_debug:
            raise err
        raise typer.Exit(code=1)
