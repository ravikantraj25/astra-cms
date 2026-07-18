"""WordPress CLI subcommands.

Provides:
- ``astra wp test``  — test the WordPress connection
- ``astra wp fetch`` — fetch posts from WordPress
- ``astra wp get``   — fetch a single post by ID
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.infrastructure.config.settings import WordPressSettings, get_wp_settings
from app.infrastructure.wordpress.client import WordPressClient
from app.infrastructure.wordpress.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import _strip_html
from app.shared.constants import APP_NAME, DEFAULT_ENCODING, OUTPUT_DIR

wp_app = typer.Typer(
    name="wp",
    help="WordPress connection and management commands.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


# ── Shared helpers ───────────────────────────────────────────────────────────


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


def _ensure_configured() -> WordPressSettings:
    """Load settings and abort if WordPress is not configured.

    Returns:
        The validated :class:`WordPressSettings`.
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

    return settings


def _handle_wp_error(exc: WordPressError) -> None:
    """Print a styled error message for any WordPress exception.

    Args:
        exc: The caught WordPress exception.
    """
    if isinstance(exc, AuthenticationError):
        console.print("  [red]✘ Authentication failed[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print("  [yellow]Hint:[/yellow] Check WP_USERNAME and WP_APP_PASSWORD in .env")
    elif isinstance(exc, ConnectionError):
        console.print("  [red]✘ Connection failed[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print("  [yellow]Hint:[/yellow] Check WP_BASE_URL and your internet connection")
    elif isinstance(exc, TimeoutError):
        console.print("  [red]✘ Request timed out[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print(
            "  [yellow]Hint:[/yellow] The site may be slow. Try increasing WP_TIMEOUT_READ"
        )
    elif isinstance(exc, RateLimitError):
        console.print("  [red]✘ Rate limited[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")
        console.print()
        console.print("  [yellow]Hint:[/yellow] Wait a moment and try again")
    else:
        console.print("  [red]✘ WordPress error[/red]")
        console.print(f"    [dim]{exc.message}[/dim]")


# ── Commands ─────────────────────────────────────────────────────────────────


@wp_app.command(name="test")
def test_connection() -> None:
    """Test the WordPress connection and display site diagnostics.

    Reads credentials from environment variables (WP_BASE_URL, WP_USERNAME,
    WP_APP_PASSWORD) and performs a health check against the WordPress REST API.
    """
    settings = _ensure_configured()

    console.print()
    console.print(f"  [dim]Connecting to[/dim] [cyan]{settings.base_url}[/cyan] [dim]...[/dim]")

    client = _create_client(settings)

    try:
        client.connect()
        console.print("  [green]✔ Connected[/green]")
        console.print()

        health = client.health_check()

        # ── Results table ────────────────────────────────────────────────
        table = Table(show_header=False, padding=(0, 2), box=None)
        table.add_column("Key", style="bold cyan", min_width=22)
        table.add_column("Value", style="white")

        table.add_row("Site Name", health.site_info.name)
        table.add_row("URL", health.site_info.url)
        table.add_row("WordPress Version", health.wp_version)
        table.add_row("Current User", health.current_user.name)

        roles_str = ", ".join(health.current_user.roles) if health.current_user.roles else "N/A"
        table.add_row("User Roles", roles_str)

        rest_status = (
            "[green]Healthy[/green]" if health.rest_api_healthy else "[red]Unhealthy[/red]"
        )
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

    except WordPressError as exc:
        _handle_wp_error(exc)
        raise typer.Exit(code=1) from exc

    finally:
        client.close()


@wp_app.command(name="fetch")
def fetch_posts(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of posts to fetch (1-100)."),
    page: int = typer.Option(1, "--page", "-p", help="Page number."),
    search: str = typer.Option("", "--search", "-s", help="Search query to filter posts."),
    status: str = typer.Option(
        "publish", "--status", help="Post status filter (publish, draft, etc.)."
    ),
) -> None:
    """Fetch posts from WordPress and display them in a table.

    Examples::

        astra wp fetch
        astra wp fetch --limit 5
        astra wp fetch --page 2
        astra wp fetch --search "Diwali"
    """
    settings = _ensure_configured()

    console.print()
    console.print("  [dim]Fetching posts...[/dim]")

    client = _create_client(settings)

    try:
        client.connect()
        console.print("  [green]✔ Connected[/green]")
        console.print()

        result = client.get_posts(per_page=limit, page=page, search=search, status=status)

        if not result.posts:
            console.print("  [yellow]No posts found.[/yellow]")
            console.print()
            raise typer.Exit(code=0)

        console.print(f"  [green]Retrieved {len(result.posts)} posts[/green]")
        console.print()

        # ── Posts table ──────────────────────────────────────────────────
        table = Table(show_header=True, header_style="bold magenta", padding=(0, 2))
        table.add_column("ID", style="cyan", justify="right", min_width=6)
        table.add_column("Status", min_width=10)
        table.add_column("Title", style="white", min_width=30)

        for post in result.posts:
            if post.status == "publish":
                status_style = "[green]publish[/green]"
            else:
                status_style = f"[yellow]{post.status}[/yellow]"
            # Strip HTML tags from title for clean display
            clean_title = post.title.replace("<br>", " ").strip()
            table.add_row(str(post.id), status_style, clean_title)

        console.print(table)
        console.print()

        # ── Pagination info ──────────────────────────────────────────────
        if result.total_pages > 1:
            console.print(
                f"  [dim]Page {result.page} of {result.total_pages}"
                f" ({result.total} total posts)[/dim]"
            )
            console.print()

    except WordPressError as exc:
        _handle_wp_error(exc)
        raise typer.Exit(code=1) from exc

    finally:
        client.close()


@wp_app.command(name="get")
def get_post(
    post_id: int = typer.Argument(help="The WordPress post ID to fetch."),
) -> None:
    """Fetch a single WordPress post and save its HTML content.

    Examples::

        astra wp get 123
        astra wp get 456
    """
    settings = _ensure_configured()

    console.print()
    console.print(f"  [dim]Fetching post {post_id}...[/dim]")

    client = _create_client(settings)

    try:
        client.connect()
        console.print("  [green]✔ Connected[/green]")
        console.print()

        detail = client.get_post(post_id)
        post = detail.post

        # ── Post details table ───────────────────────────────────────────
        table = Table(show_header=False, padding=(0, 2), box=None)
        table.add_column("Key", style="bold cyan", min_width=16)
        table.add_column("Value", style="white")

        table.add_row("ID", str(post.id))
        table.add_row("Title", _strip_html(post.title))

        if post.status == "publish":
            table.add_row("Status", "[green]publish[/green]")
        else:
            table.add_row("Status", f"[yellow]{post.status}[/yellow]")

        table.add_row("Author", detail.author_name)

        # Show date (just the date part if ISO 8601)
        display_date = post.date[:10] if len(post.date) >= 10 else post.date
        table.add_row("Date", display_date)

        table.add_row("Categories", ", ".join(detail.categories) or "None")
        table.add_row("Tags", ", ".join(detail.tags) or "None")
        table.add_row("Word Count", str(detail.word_count))

        console.print(
            Panel(
                table,
                border_style="bright_blue",
                title=f"[bold]{APP_NAME}[/bold] — Post #{post.id}",
                padding=(1, 2),
            )
        )
        console.print()

        # ── Save raw HTML ────────────────────────────────────────────────
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"post_{post.id}.html"
        output_file.write_text(post.content_html, encoding=DEFAULT_ENCODING)

        console.print(f"  [green]✔ Saved HTML to[/green] [cyan]{output_file}[/cyan]")
        console.print()

    except WordPressError as exc:
        _handle_wp_error(exc)
        raise typer.Exit(code=1) from exc

    finally:
        client.close()
