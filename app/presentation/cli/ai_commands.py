"""AI CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.infrastructure.config.settings import get_groq_settings
from app.infrastructure.providers.groq_provider import GroqProvider

ai_app = typer.Typer(
    name="ai",
    help="AI provider management and generation commands.",
    no_args_is_help=True,
)
console = Console()


@ai_app.command(name="health")
def ai_health() -> None:
    """Check the health and configuration of the active AI Provider."""
    console.print()
    console.print("  Checking AI provider health...")
    console.print()

    settings = get_groq_settings()
    provider = "Groq (OpenAI Compatible)"
    model = settings.model

    status = "[red]Not Configured[/red]"
    if settings.is_configured:
        try:
            # We perform a lightweight call, or just instantiate and try a basic generate
            # But the prompt says "Connection Status". A simple query is a bit expensive
            # We can just attempt to generate a tiny string or hit a models endpoint.
            # For simplicity, we just send a "hello" prompt with max_tokens=1 if possible,
            # or we just rely on GroqProvider generating a short message.
            groq_provider = GroqProvider(settings)

            # Hit the models endpoint instead of generating text to save tokens
            # Using the existing http_client from the provider
            resp = groq_provider.http_client.get("/models")
            resp.raise_for_status()

            status = "[green]Connected[/green]"
        except Exception:
            status = "[red]Connection Failed[/red]"

    table = Table(show_header=True, header_style="bold magenta", padding=(0, 2), box=None)
    table.add_column("Provider", style="cyan")
    table.add_column("Model", style="white")
    table.add_column("Connection Status", style="dim")

    table.add_row(provider, model, status)

    console.print(
        Panel(
            table,
            border_style="bright_blue",
            title="[bold]AI Health Status[/bold]",
            padding=(1, 2),
        )
    )
    console.print()
