"""WordPress CLI subcommands.

Provides ``astra wp test`` for testing the WordPress connection.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.infrastructure.config.settings import WordPressSettings, get_wp_settings
from app.infrastructure.wordpress.client import WordPressClient
from app.infrastructure.wordpress.exceptions import (
    AuthenticationError,
    ConnectionError,
    TimeoutError,
    WordPressError,
)
from app.shared.constants import APP_NAME

wp_app = typer.Typer(
    name="wp",
    help="WordPress connection and management commands.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def _create_client(settings: WordPressSettings) -> WordPressClient:
    """Create a WordPressClient from the current settings.

    Args:
        settings: The WordPress settings instance.

    Returns:
        A configured :class:`WordPressClient`.
    """
    return WordPressClient(
        base_url=settings.base_url,
        username=settings.username,
        app_password=settings.app_password.get_secret_value(),
        timeout=(settings.timeout_connect, settings.timeout_read),
        verify_ssl=settings.verify_ssl,
    )


@wp_app.command(name="test")
def test_connection() -> None:
    """Test the WordPress connection and display site diagnostics.

    Reads credentials from environment variables (WP_BASE_URL, WP_USERNAME,
    WP_APP_PASSWORD) and performs a health check against the WordPress REST API.
    """
    settings = get_wp_settings()

    if not settings.is_configured:
        console.print()
        console.print(
            Panel.fit(
                "[bold red]WordPress is not configured.[/bold red]\n\n"
                "Set the following environment variables in your [cyan].env[/cyan] file:\n\n"
                "  [dim]WP_BASE_URL[/dim]      = https://your-site.com\n"
                "  [dim]WP_USERNAME[/dim]      = your-username\n"
                "  [dim]WP_APP_PASSWORD[/dim]  = xxxx xxxx xxxx xxxx",
                border_style="red",
                title="Configuration Missing",
                padding=(1, 2),
            )
        )
        raise typer.Exit(code=1)

    console.print()
    console.print(f"  [dim]Connecting to[/dim] [cyan]{settings.base_url}[/cyan] [dim]...[/dim]")

    client = _create_client(settings)

    try:
        client.connect()
        console.print("  [green]✔ Connected[/green]")
        console.print()

        health = client.health_check()

        # ── Results table ────────────────────────────────────────────────
        table = Table(
            show_header=False,
            padding=(0, 2),
            box=None,
        )
        table.add_column("Key", style="bold cyan", min_width=22)
        table.add_column("Value", style="white")

        table.add_row("Site Name", health.site_info.name)
        table.add_row("URL", health.site_info.url)
        table.add_row("WordPress Version", health.wp_version)
        table.add_row("Current User", health.current_user.name)

        roles_str = ", ".join(health.current_user.roles) if health.current_user.roles else "N/A"
        table.add_row("User Roles", roles_str)

        rest_status = "[green]Healthy[/green]" if health.rest_api_healthy else "[red]Unhealthy[/red]"
        table.add_row("REST API", rest_status)

        console.print(
            Panel(
                table,
                border_style="bright_blue",
                title=f"[bold]{APP_NAME}[/bold] — WordPress Connection",
                padding=(1, 2),
            )
        )
        console.print()

    except AuthenticationError as exc:
        console.print(f"  [red]✘ Authentication failed[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print("  [yellow]Hint:[/yellow] Check WP_USERNAME and WP_APP_PASSWORD in .env")
        raise typer.Exit(code=1) from exc

    except ConnectionError as exc:
        console.print(f"  [red]✘ Connection failed[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print("  [yellow]Hint:[/yellow] Check WP_BASE_URL and your internet connection")
        raise typer.Exit(code=1) from exc

    except TimeoutError as exc:
        console.print(f"  [red]✘ Request timed out[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print("  [yellow]Hint:[/yellow] The site may be slow. Try increasing WP_TIMEOUT_READ")
        raise typer.Exit(code=1) from exc

    except WordPressError as exc:
        console.print(f"  [red]✘ WordPress error[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        raise typer.Exit(code=1) from exc

    finally:
        client.close()
