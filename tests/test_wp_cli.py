"""Tests for the ``astra wp test``, ``astra wp fetch``, and ``astra wp get`` CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.infrastructure.wordpress.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import (
    WPHealthCheck,
    WPPost,
    WPPostDetail,
    WPPostList,
    WPSiteInfo,
    WPUser,
)
from app.presentation.cli.main import cli


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture()
def mock_wp_settings() -> MagicMock:
    """Return a mock WordPressSettings that is fully configured."""
    return MagicMock(
        is_configured=True,
        base_url="https://example.com",
        username="admin",
        app_password=MagicMock(get_secret_value=MagicMock(return_value="test-pass")),
        timeout_connect=10.0,
        timeout_read=30.0,
        verify_ssl=True,
    )


@pytest.fixture()
def mock_health() -> WPHealthCheck:
    """Return a mock WPHealthCheck result."""
    return WPHealthCheck(
        site_info=WPSiteInfo(
            name="LokGeets",
            description="A test site",
            url="https://example.com",
            home="https://example.com",
            namespaces=["wp/v2"],
        ),
        current_user=WPUser(
            id=1,
            name="admin",
            slug="admin",
            roles=["administrator"],
        ),
        wp_version="6.5.2",
        rest_api_healthy=True,
    )


@pytest.fixture()
def mock_post_list() -> WPPostList:
    """Return a mock WPPostList result."""
    return WPPostList(
        posts=[
            WPPost(id=120, title="Diwali NYC 2026", status="publish", slug="diwali"),
            WPPost(id=121, title="Chhath USA", status="publish", slug="chhath"),
            WPPost(id=122, title="Holi Boston", status="draft", slug="holi"),
        ],
        total=3,
        total_pages=1,
        page=1,
        per_page=10,
    )


# =============================================================================
# astra wp test
# =============================================================================


class TestWPTestCommand:
    """Tests for ``astra wp test``."""

    def test_wp_test_not_configured(self, cli_runner: CliRunner) -> None:
        """Should fail gracefully when WordPress is not configured."""
        with patch("app.presentation.cli.wp_commands.get_wp_settings") as mock_settings:
            mock_settings.return_value = MagicMock(is_configured=False)

            result = cli_runner.invoke(cli, ["wp", "test"])
            assert result.exit_code == 1
            assert "not configured" in result.output.lower()

    def test_wp_test_success(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_health: WPHealthCheck,
    ) -> None:
        """Should display site info on successful connection."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.health_check.return_value = mock_health

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 0
            assert "Connected" in result.output
            assert "LokGeets" in result.output
            assert "admin" in result.output
            assert "Healthy" in result.output

    def test_wp_test_auth_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show auth error and hint on 401."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = AuthenticationError("Bad credentials")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "Authentication failed" in result.output

    def test_wp_test_connection_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show connection error and hint on network failure."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = ConnectionError("DNS failed")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "Connection failed" in result.output

    def test_wp_test_timeout_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show timeout error and hint."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = TimeoutError("Request timed out")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "timed out" in result.output

    def test_wp_test_generic_wp_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show generic WordPress error message."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = WordPressError("REST API disabled")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "WordPress error" in result.output


# =============================================================================
# astra wp fetch
# =============================================================================


class TestWPFetchCommand:
    """Tests for ``astra wp fetch``."""

    def test_fetch_not_configured(self, cli_runner: CliRunner) -> None:
        """Should fail gracefully when WordPress is not configured."""
        with patch("app.presentation.cli.wp_commands.get_wp_settings") as mock_settings:
            mock_settings.return_value = MagicMock(is_configured=False)

            result = cli_runner.invoke(cli, ["wp", "fetch"])
            assert result.exit_code == 1
            assert "not configured" in result.output.lower()

    def test_fetch_success(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_post_list: WPPostList,
    ) -> None:
        """Should display posts in a table on success."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_posts.return_value = mock_post_list

            result = cli_runner.invoke(cli, ["wp", "fetch"])

            assert result.exit_code == 0
            assert "Connected" in result.output
            assert "Retrieved 3 posts" in result.output
            assert "Diwali NYC 2026" in result.output
            assert "Chhath USA" in result.output
            assert "Holi Boston" in result.output
            assert "120" in result.output

    def test_fetch_empty_result(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should display 'no posts found' when result is empty."""
        empty_list = WPPostList(posts=[], total=0, total_pages=0, page=1, per_page=10)

        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_posts.return_value = empty_list

            result = cli_runner.invoke(cli, ["wp", "fetch"])

            assert result.exit_code == 0
            assert "No posts found" in result.output

    def test_fetch_with_limit(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_post_list: WPPostList,
    ) -> None:
        """Should pass --limit to get_posts()."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_posts.return_value = mock_post_list

            result = cli_runner.invoke(cli, ["wp", "fetch", "--limit", "5"])

            assert result.exit_code == 0
            mock_instance.get_posts.assert_called_once_with(
                per_page=5, page=1, search="", status="publish"
            )

    def test_fetch_with_search(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_post_list: WPPostList,
    ) -> None:
        """Should pass --search to get_posts()."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_posts.return_value = mock_post_list

            result = cli_runner.invoke(cli, ["wp", "fetch", "--search", "Diwali"])

            assert result.exit_code == 0
            mock_instance.get_posts.assert_called_once_with(
                per_page=10, page=1, search="Diwali", status="publish"
            )

    def test_fetch_with_page(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_post_list: WPPostList,
    ) -> None:
        """Should pass --page to get_posts()."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_posts.return_value = mock_post_list

            result = cli_runner.invoke(cli, ["wp", "fetch", "--page", "2"])

            assert result.exit_code == 0
            mock_instance.get_posts.assert_called_once_with(
                per_page=10, page=2, search="", status="publish"
            )

    def test_fetch_auth_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show auth error for fetch command."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = AuthenticationError("Bad credentials")

            result = cli_runner.invoke(cli, ["wp", "fetch"])

            assert result.exit_code == 1
            assert "Authentication failed" in result.output

    def test_fetch_rate_limit_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show rate limit error for fetch command."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = RateLimitError()

            result = cli_runner.invoke(cli, ["wp", "fetch"])

            assert result.exit_code == 1
            assert "Rate limited" in result.output

    def test_fetch_pagination_info(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show pagination info when multiple pages exist."""
        multi_page_list = WPPostList(
            posts=[WPPost(id=1, title="Test Post", status="publish", slug="test")],
            total=30,
            total_pages=3,
            page=1,
            per_page=10,
        )

        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_posts.return_value = multi_page_list

            result = cli_runner.invoke(cli, ["wp", "fetch"])

            assert result.exit_code == 0
            assert "Page 1 of 3" in result.output
            assert "30 total posts" in result.output


# =============================================================================
# Help / Discovery
# =============================================================================


class TestWPHelpCommand:
    """Tests for the ``astra wp`` help output."""

    def test_wp_help(self, cli_runner: CliRunner) -> None:
        """``astra wp --help`` should list test, fetch, and get commands."""
        result = cli_runner.invoke(cli, ["wp", "--help"])
        assert result.exit_code == 0
        assert "test" in result.output
        assert "fetch" in result.output
        assert "get" in result.output

    def test_main_help_includes_wp(self, cli_runner: CliRunner) -> None:
        """``astra --help`` should show the wp subcommand."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "wp" in result.output


# =============================================================================
# astra wp get
# =============================================================================


class TestWPGetCommand:
    """Tests for ``astra wp get <post_id>``."""

    @pytest.fixture()
    def mock_post_detail(self) -> WPPostDetail:
        """Return a mock WPPostDetail result."""
        return WPPostDetail(
            post=WPPost(
                id=123,
                title="Diwali Celebration NYC",
                status="publish",
                slug="diwali-celebration-nyc",
                date="2026-09-20T10:00:00",
                content_html="<p>Diwali is the festival of lights.</p>",
                author=1,
            ),
            author_name="Admin",
            categories=["Festivals"],
            tags=["Diwali", "USA"],
            word_count=6,
        )

    def test_get_not_configured(self, cli_runner: CliRunner) -> None:
        """Should fail gracefully when WordPress is not configured."""
        with patch("app.presentation.cli.wp_commands.get_wp_settings") as mock_settings:
            mock_settings.return_value = MagicMock(is_configured=False)

            result = cli_runner.invoke(cli, ["wp", "get", "123"])
            assert result.exit_code == 1
            assert "not configured" in result.output.lower()

    def test_get_success(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_post_detail: WPPostDetail,
        tmp_path: object,
    ) -> None:
        """Should display post details and save HTML on success."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
            patch("app.presentation.cli.wp_commands.Path") as MockPath,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_post.return_value = mock_post_detail

            # Mock the Path operations
            mock_dir = MagicMock()
            MockPath.return_value = mock_dir
            mock_file = MagicMock()
            mock_dir.__truediv__ = MagicMock(return_value=mock_file)

            result = cli_runner.invoke(cli, ["wp", "get", "123"])

            assert result.exit_code == 0
            assert "Connected" in result.output
            assert "Diwali Celebration NYC" in result.output
            assert "Admin" in result.output
            assert "Festivals" in result.output
            assert "Diwali, USA" in result.output
            assert "7" in result.output
            assert "2026-09-20" in result.output
            mock_instance.get_post.assert_called_once_with(123)

    def test_get_404(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show error when post is not found."""
        from app.infrastructure.wordpress.exceptions import APIError

        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.return_value = None
            mock_instance.get_post.side_effect = APIError(
                message="WordPress API error (HTTP 404): Post not found",
                status_code=404,
            )

            result = cli_runner.invoke(cli, ["wp", "get", "99999"])

            assert result.exit_code == 1
            assert "WordPress error" in result.output

    def test_get_auth_error(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
    ) -> None:
        """Should show auth error for get command."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = AuthenticationError("Bad credentials")

            result = cli_runner.invoke(cli, ["wp", "get", "123"])

            assert result.exit_code == 1
            assert "Authentication failed" in result.output

    def test_get_saves_html_file(
        self,
        cli_runner: CliRunner,
        mock_wp_settings: MagicMock,
        mock_post_detail: WPPostDetail,
    ) -> None:
        """Should save the raw HTML content to output/post_{id}.html."""
        with (
            patch(
                "app.presentation.cli.wp_commands.get_wp_settings",
                return_value=mock_wp_settings,
            ),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
            patch("app.presentation.cli.wp_commands.Path") as MockPath,
        ):
            mock_instance = MockClient.return_value
            mock_instance.get_post.return_value = mock_post_detail

            mock_output_dir = MagicMock()
            MockPath.return_value = mock_output_dir
            mock_file = MagicMock()
            mock_output_dir.__truediv__ = MagicMock(return_value=mock_file)

            result = cli_runner.invoke(cli, ["wp", "get", "123"])

            assert result.exit_code == 0
            # Verify mkdir was called
            mock_output_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # Verify write_text was called with HTML content
            mock_file.write_text.assert_called_once_with(
                "<p>Diwali is the festival of lights.</p>",
                encoding="utf-8",
            )
