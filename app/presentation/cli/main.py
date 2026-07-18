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
from importlib.metadata import version as pkg_version
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app import __version__
from app.application.parser import parse_html_file
from app.presentation.cli.ai_commands import ai_app
from app.presentation.cli.wp_commands import wp_app
from app.shared.constants import APP_NAME

# ── Typer App ────────────────────────────────────────────────────────────────

cli = typer.Typer(
    name="astra",
    help=f"{APP_NAME} — AI-powered headless CMS toolkit.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

cli.add_typer(wp_app, name="wp")
cli.add_typer(ai_app, name="ai")

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


# ── Helpers ──────────────────────────────────────────────────────────────────


def _status_icon(ok: bool) -> str:
    """Return a coloured status icon."""
    return "[green]✔[/green]" if ok else "[red]✘[/red]"


def _check_package(table: Table, name: str) -> None:
    """Add a row for an installed Python package."""
    try:
        ver: str | None = pkg_version(name)
        table.add_row(f"Package: {name}", _status_icon(True), f"v{ver}")
    except Exception:
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
