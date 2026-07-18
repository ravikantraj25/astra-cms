"""Astra CMS — Typer CLI entry-point.

Registers top-level commands and sub-command groups.  Each command is a thin
adapter that delegates to the application layer.

Usage::

    astra version
    astra doctor
    astra wp test
    astra wp fetch
"""

from __future__ import annotations

import platform
import shutil
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app import __version__
from app.application.parser import parse_html_file
from app.presentation.cli.ai_commands import ai_app
from app.presentation.cli.auto_commands import auto_app
from app.presentation.cli.workflow_commands import workflow_app
from app.presentation.cli.wp_commands import wp_app
from app.shared.constants import APP_NAME

# ── Typer App ────────────────────────────────────────────────────────────────

cli = typer.Typer(
    name="astra",
    help=f"{APP_NAME} — AI-powered Editorial Operating System for WordPress.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

cli.add_typer(wp_app, name="wp")
cli.add_typer(ai_app, name="ai")
cli.add_typer(workflow_app, name="workflow")
cli.add_typer(auto_app, name="auto")

console = Console()


# ── Commands ─────────────────────────────────────────────────────────────────


@cli.command()
def version(
    short: bool = typer.Option(False, "--short", "-s", help="Print only the version number."),
) -> None:
    """Display the current Astra CMS version."""
    if short:
        console.print(__version__)
        return

    console.print(
        Panel.fit(
            f"[bold cyan]{APP_NAME}[/bold cyan]  [dim]v{__version__}[/dim]",
            border_style="bright_blue",
            padding=(1, 4),
        )
    )


@cli.command()
def doctor() -> None:
    """Run system diagnostics and report environment health.

    Checks Python version, installed packages, and required external tools
    to help troubleshoot common setup issues.
    """
    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]{APP_NAME}[/bold cyan] — System Diagnostics",
            border_style="bright_blue",
            padding=(0, 2),
        )
    )
    console.print()

    table = Table(show_header=True, header_style="bold magenta", padding=(0, 2))
    table.add_column("Check", style="cyan", min_width=24)
    table.add_column("Status", justify="center", min_width=8)
    table.add_column("Details", style="dim")

    # ── Python version ───────────────────────────────────────────────────
    py_version = platform.python_version()
    py_ok = sys.version_info >= (3, 11)
    table.add_row(
        "Python version",
        _status_icon(py_ok),
        f"{py_version} ({'≥3.11' if py_ok else 'requires ≥3.11'})",
    )

    # ── Core packages ────────────────────────────────────────────────────
    _check_package(table, "typer")
    _check_package(table, "pydantic")
    _check_package(table, "rich")

    # ── Dev tools ────────────────────────────────────────────────────────
    _check_binary(table, "uv")
    _check_binary(table, "git")
    _check_binary(table, "docker")

    console.print(table)
    console.print()


@cli.command(name="parse")
def parse_html(
    file_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the HTML file to parse.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Parse an HTML file and display the extracted Article structure."""
    try:
        article = parse_html_file(file_path)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{file_path}[/dim]")
        raise typer.Exit(code=1) from err

    console.print()
    console.print(f"  [dim]Parsed[/dim] [cyan]{file_path}[/cyan]")
    console.print()

    table = Table(show_header=False, padding=(0, 2), box=None)
    table.add_column("Key", style="bold magenta", min_width=16)
    table.add_column("Value", style="white")

    table.add_row("Title", article.title or "[dim]None[/dim]")
    table.add_row("Word count", str(article.word_count))
    table.add_row("Images", str(len(article.images)))
    table.add_row("Links", str(len(article.links)))
    table.add_row("Tables", str(len(article.tables)))
    table.add_row("Headings", str(len(article.headings)))

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — Parsing Summary",
            padding=(1, 2),
        )
    )
    console.print()


@cli.command(name="analyze")
def analyze_html(
    file_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the HTML file to analyze.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Analyze an HTML file to detect semantic sections."""
    try:
        from app.application.section_detector import detect_sections

        article = parse_html_file(file_path)
        article = detect_sections(article)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{file_path}[/dim]")
        raise typer.Exit(code=1) from err

    console.print()
    console.print(f"  [dim]Analyzed[/dim] [cyan]{file_path}[/cyan]")
    console.print()

    if not article.sections:
        console.print("  [yellow]No sections detected.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta", padding=(0, 2), box=None)
    table.add_column("Type", style="cyan", min_width=16)
    table.add_column("Name", style="white")
    table.add_column("Pos (Start-End)", style="dim")

    for section in article.sections:
        table.add_row(
            section.type,
            section.name,
            f"{section.start_position}-{section.end_position}",
        )

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — Detected Sections",
            padding=(1, 2),
        )
    )
    console.print()


@cli.command(name="prompt")
def generate_prompt(
    file_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the HTML file to build a prompt from.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Build an AI prompt from a parsed HTML file and save to output/prompt.txt."""
    from app.application.prompt_builder import build_prompt
    from app.application.section_detector import detect_sections

    try:
        article = parse_html_file(file_path)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{file_path}[/dim]")
        raise typer.Exit(code=1) from err

    article = detect_sections(article)
    prompt_text = build_prompt(article)

    # Save to output/prompt.txt
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "prompt.txt"
    output_file.write_text(prompt_text, encoding="utf-8")

    console.print()
    console.print(f"  [dim]Parsed[/dim]    [cyan]{file_path}[/cyan]")
    console.print(f"  [dim]Sections[/dim]  [cyan]{len(article.sections)} detected[/cyan]")
    console.print()

    table = Table(show_header=False, padding=(0, 2), box=None)
    table.add_column("Key", style="bold magenta", min_width=16)
    table.add_column("Value", style="white")

    table.add_row("Title", article.title or "[dim]Untitled[/dim]")
    table.add_row("Word Count", str(article.word_count))
    table.add_row("Sections", str(len(article.sections)))
    table.add_row("Prompt Length", f"{len(prompt_text)} chars")
    table.add_row("Saved To", str(output_file))

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — Prompt Generated",
            padding=(1, 2),
        )
    )
    console.print()


@cli.command(name="analyze-ai")
def analyze_article_ai(
    file_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the HTML file to analyze with AI.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Analyze an HTML file using Groq AI and save JSON output."""
    import json

    from app.application.prompt_builder import build_analysis_prompt
    from app.infrastructure.config.settings import get_groq_settings
    from app.infrastructure.providers.groq_provider import GroqProvider

    try:
        article = parse_html_file(file_path)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{file_path}[/dim]")
        raise typer.Exit(code=1) from err

    settings = get_groq_settings()
    if not settings.is_configured:
        console.print("  [red]✘ Groq API key is not configured.[/red]")
        console.print("  [dim]Please set GROQ_API_KEY in your .env file.[/dim]")
        raise typer.Exit(code=1)

    console.print()
    console.print(f"  [dim]Analyzing[/dim] [cyan]{file_path}[/cyan] [dim]with Groq AI...[/dim]")

    prompt = build_analysis_prompt(article)
    provider = GroqProvider(settings)

    try:
        response_text = provider.generate(prompt)
    except (ValueError, RuntimeError) as e:
        console.print(f"  [red]✘ AI Generation failed:[/red] {e}")
        raise typer.Exit(code=1) from e

    # Clean the response in case the AI added markdown blocks despite instructions
    clean_text = response_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    try:
        parsed_json = json.loads(clean_text)
    except json.JSONDecodeError:
        console.print("  [yellow]⚠ AI did not return valid JSON. Saving raw output.[/yellow]")
        parsed_json = {"raw_output": clean_text}

    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "analysis.json"
    output_file.write_text(json.dumps(parsed_json, indent=2), encoding="utf-8")

    console.print()
    table = Table(show_header=False, padding=(0, 2), box=None)
    table.add_column("Key", style="bold magenta", min_width=16)
    table.add_column("Value", style="white")

    table.add_row("Status", "[green]Success[/green]")
    table.add_row("Saved To", str(output_file))

    if "seo_score" in parsed_json:
        table.add_row("SEO Score", str(parsed_json["seo_score"]))
    if "readability_score" in parsed_json:
        table.add_row("Readability", str(parsed_json["readability_score"]))

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — AI Analysis",
            padding=(1, 2),
        )
    )
    console.print()

    console.print()


@cli.command(name="plan")
def generate_plan(
    analysis_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the JSON analysis file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    article_path: Path = typer.Option(  # noqa: B008
        None,
        "--article",
        "-a",
        help=(
            "Path to the original HTML file. If not provided, it will try to "
            "find one in the same directory."
        ),
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Generate an Update Plan from an article and its AI analysis."""
    import json

    from app.application.planner import build_update_plan
    from app.application.section_detector import detect_sections

    try:
        analysis_data = json.loads(analysis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        console.print(f"  [red]✘ Invalid JSON in analysis file:[/red] [dim]{analysis_path}[/dim]")
        raise typer.Exit(code=1) from err

    # Resolve article path if not provided
    if not article_path:
        html_files = list(analysis_path.parent.glob("*.html"))
        if len(html_files) == 1:
            article_path = html_files[0]
        elif len(html_files) > 1:
            console.print("  [red]✘ Multiple HTML files found. Please specify --article.[/red]")
            raise typer.Exit(code=1)
        else:
            console.print(
                "  [red]✘ No HTML files found in the directory. Please specify --article.[/red]"
            )
            raise typer.Exit(code=1)

    try:
        article = parse_html_file(article_path)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{article_path}[/dim]")
        raise typer.Exit(code=1) from err

    article = detect_sections(article)
    plan = build_update_plan(article, analysis_data)

    output_dir = analysis_path.parent
    output_file = output_dir / "update_plan.json"

    # Save the plan
    plan_dict = plan.model_dump()
    output_file.write_text(json.dumps(plan_dict, indent=2), encoding="utf-8")

    console.print()
    console.print(f"  [dim]Generated Plan for[/dim] [cyan]{article_path}[/cyan]")
    console.print()

    if not plan.actions:
        console.print("  [yellow]No actions in plan.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta", padding=(0, 2), box=None)
    table.add_column("Section", style="cyan")
    table.add_column("Reason", style="white")
    table.add_column("Priority", style="dim")
    table.add_column("Confidence", style="magenta")
    table.add_column("Action", style="bold green")

    for action in plan.actions:
        action_style = (
            "[bold green]Update[/bold green]" if action.action == "Update" else "[dim]Skip[/dim]"
        )
        table.add_row(
            action.section,
            action.reason,
            action.priority,
            f"{action.confidence}%",
            action_style,
        )

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — Update Plan",
            padding=(1, 2),
        )
    )
    console.print()
    console.print(f"  [dim]Saved To:[/dim] {output_file}")
    console.print()


@cli.command(name="diff")
def diff_articles(
    original_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the original HTML file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    updated_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the AI-updated HTML file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Compare original HTML with AI output and generate a DiffReport."""
    import json

    from app.application.differ import build_diff_report

    try:
        original = parse_html_file(original_path)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{original_path}[/dim]")
        raise typer.Exit(code=1) from err

    try:
        updated = parse_html_file(updated_path)
    except FileNotFoundError as err:
        console.print(f"  [red]✘ File not found:[/red] [dim]{updated_path}[/dim]")
        raise typer.Exit(code=1) from err

    report = build_diff_report(original, updated)

    output_dir = original_path.parent
    output_file = output_dir / "update_diff.json"

    # Save the report
    report_dict = report.model_dump()
    output_file.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

    console.print()
    console.print(
        f"  [dim]Compared[/dim] [cyan]{original_path.name}[/cyan] [dim]with[/dim] "
        f"[cyan]{updated_path.name}[/cyan]"
    )
    console.print()

    table = Table(show_header=True, header_style="bold magenta", padding=(0, 2), box=None)
    table.add_column("Type", style="cyan")
    table.add_column("Content (Snippet)", style="white")
    table.add_column("Confidence", style="magenta")
    table.add_column("Reason", style="dim")

    for action in report.added:
        table.add_row(
            "[green]Added[/green]", action.content, f"{action.confidence}%", action.reason
        )
    for action in report.removed:
        table.add_row("[red]Removed[/red]", action.content, f"{action.confidence}%", action.reason)
    for action in report.modified:
        table.add_row(
            "[yellow]Modified[/yellow]", action.content, f"{action.confidence}%", action.reason
        )

    if not (report.added or report.removed or report.modified):
        table.add_row("[dim]None[/dim]", "[dim]No differences found.[/dim]", "-", "-")

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — Update Diff Report",
            padding=(1, 2),
        )
    )
    console.print()
    console.print(f"  [dim]Saved To:[/dim] {output_file}")
    console.print()


@cli.command(name="generate")
def generate_html(
    plan_path: Path = typer.Argument(  # noqa: B008
        ...,
        help="Path to the update_plan.json file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    article_path: Path = typer.Option(  # noqa: B008
        None,
        "--article",
        "-a",
        help="Path to the original HTML file. If omitted, attempts auto-discovery.",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
) -> None:
    """Generate updated HTML from an Update Plan using AI."""
    import json

    from app.application.generator import generate_updated_article
    from app.application.section_detector import detect_sections
    from app.domain.plan import UpdatePlan
    from app.infrastructure.config.settings import get_groq_settings
    from app.infrastructure.providers.groq_provider import GroqProvider

    settings = get_groq_settings()
    if not settings.is_configured:
        console.print("  [red]✘ Groq API key is not configured.[/red]")
        raise typer.Exit(code=1)

    try:
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        plan = UpdatePlan.model_validate(plan_data)
    except (json.JSONDecodeError, ValueError) as err:
        console.print(f"  [red]✘ Invalid Plan file:[/red] {err}")
        raise typer.Exit(code=1) from err

    if not article_path:
        html_files = list(plan_path.parent.glob("*.html"))
        if len(html_files) == 1:
            article_path = html_files[0]
        elif len(html_files) > 1:
            console.print("  [red]✘ Multiple HTML files found. Please specify --article.[/red]")
            raise typer.Exit(code=1)
        else:
            console.print("  [red]✘ No HTML files found. Please specify --article.[/red]")
            raise typer.Exit(code=1)

    try:
        article = parse_html_file(article_path)
        article = detect_sections(article)
    except (FileNotFoundError, ValueError, OSError) as err:
        console.print(f"  [red]✘ Failed to parse article:[/red] {err}")
        raise typer.Exit(code=1) from err

    console.print()
    console.print(
        f"  [dim]Generating HTML for[/dim] [cyan]{article_path.name}[/cyan] [dim]...[/dim]"
    )

    provider = GroqProvider(settings)
    updated_html, _ = generate_updated_article(article, plan, provider)

    output_dir = plan_path.parent
    output_file = output_dir / f"{article_path.stem}_updated.html"
    output_file.write_text(updated_html, encoding="utf-8")

    console.print()
    table = Table(show_header=False, padding=(0, 2), box=None)
    table.add_column("Key", style="bold magenta", min_width=16)
    table.add_column("Value", style="white")
    table.add_row("Status", "[green]Success[/green]")
    table.add_row("Original Size", f"{len(article.raw_html)} chars")
    table.add_row("Updated Size", f"{len(updated_html)} chars")
    table.add_row("Saved To", str(output_file))

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title=f"[bold]{APP_NAME}[/bold] — HTML Generation Complete",
            padding=(1, 2),
        )
    )
    console.print()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _status_icon(ok: bool) -> str:
    """Return a coloured status icon."""
    return "[green]✔[/green]" if ok else "[red]✘[/red]"


def _check_package(table: Table, name: str) -> None:
    """Add a row for an installed Python package."""
    try:
        ver: str | None = pkg_version(name)
        table.add_row(f"Package: {name}", _status_icon(True), f"v{ver}")
    except PackageNotFoundError:
        table.add_row(f"Package: {name}", _status_icon(False), "not installed")


def _check_binary(table: Table, name: str) -> None:
    """Add a row for an external binary on ``$PATH``."""
    path = shutil.which(name)
    if path:
        table.add_row(f"Binary: {name}", _status_icon(True), path)
    else:
        table.add_row(f"Binary: {name}", _status_icon(False), "not found")


# ── Direct Invocation ────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
