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

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app import __version__
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
