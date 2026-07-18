"""Tests for the ``astra wp test`` CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.infrastructure.wordpress.exceptions import (
    AuthenticationError,
    ConnectionError,
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import WPHealthCheck, WPSiteInfo, WPUser
from app.presentation.cli.main import cli


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


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




class TestWPTestCommand:
    """Tests for ``astra wp test``."""

    def test_wp_test_not_configured(self, cli_runner: CliRunner) -> None:
        """Should fail gracefully when WordPress is not configured."""
        with patch(
            "app.presentation.cli.wp_commands.get_wp_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(is_configured=False)

            result = cli_runner.invoke(cli, ["wp", "test"])
            assert result.exit_code == 1
            assert "not configured" in result.output.lower()

    def test_wp_test_success(
        self,
        cli_runner: CliRunner,
        mock_health: WPHealthCheck,
    ) -> None:
        """Should display site info on successful connection."""
        mock_settings = MagicMock(
            is_configured=True,
            base_url="https://example.com",
            username="admin",
            app_password=MagicMock(get_secret_value=MagicMock(return_value="test-pass")),
            timeout_connect=10.0,
            timeout_read=30.0,
            verify_ssl=True,
        )

        with (
            patch("app.presentation.cli.wp_commands.get_wp_settings", return_value=mock_settings),
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

    def test_wp_test_auth_error(self, cli_runner: CliRunner) -> None:
        """Should show auth error and hint on 401."""
        mock_settings = MagicMock(
            is_configured=True,
            base_url="https://example.com",
            username="admin",
            app_password=MagicMock(get_secret_value=MagicMock(return_value="bad-pass")),
            timeout_connect=10.0,
            timeout_read=30.0,
            verify_ssl=True,
        )

        with (
            patch("app.presentation.cli.wp_commands.get_wp_settings", return_value=mock_settings),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = AuthenticationError("Bad credentials")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "Authentication failed" in result.output

    def test_wp_test_connection_error(self, cli_runner: CliRunner) -> None:
        """Should show connection error and hint on network failure."""
        mock_settings = MagicMock(
            is_configured=True,
            base_url="https://example.com",
            username="admin",
            app_password=MagicMock(get_secret_value=MagicMock(return_value="pass")),
            timeout_connect=10.0,
            timeout_read=30.0,
            verify_ssl=True,
        )

        with (
            patch("app.presentation.cli.wp_commands.get_wp_settings", return_value=mock_settings),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = ConnectionError("DNS failed")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "Connection failed" in result.output

    def test_wp_test_timeout_error(self, cli_runner: CliRunner) -> None:
        """Should show timeout error and hint."""
        mock_settings = MagicMock(
            is_configured=True,
            base_url="https://example.com",
            username="admin",
            app_password=MagicMock(get_secret_value=MagicMock(return_value="pass")),
            timeout_connect=10.0,
            timeout_read=30.0,
            verify_ssl=True,
        )

        with (
            patch("app.presentation.cli.wp_commands.get_wp_settings", return_value=mock_settings),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = TimeoutError("Request timed out")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "timed out" in result.output

    def test_wp_test_generic_wp_error(self, cli_runner: CliRunner) -> None:
        """Should show generic WordPress error message."""
        mock_settings = MagicMock(
            is_configured=True,
            base_url="https://example.com",
            username="admin",
            app_password=MagicMock(get_secret_value=MagicMock(return_value="pass")),
            timeout_connect=10.0,
            timeout_read=30.0,
            verify_ssl=True,
        )

        with (
            patch("app.presentation.cli.wp_commands.get_wp_settings", return_value=mock_settings),
            patch("app.presentation.cli.wp_commands.WordPressClient") as MockClient,
        ):
            mock_instance = MockClient.return_value
            mock_instance.connect.side_effect = WordPressError("REST API disabled")

            result = cli_runner.invoke(cli, ["wp", "test"])

            assert result.exit_code == 1
            assert "WordPress error" in result.output


class TestWPHelpCommand:
    """Tests for the ``astra wp`` help output."""

    def test_wp_help(self, cli_runner: CliRunner) -> None:
        """``astra wp --help`` should list the test command."""
        result = cli_runner.invoke(cli, ["wp", "--help"])
        assert result.exit_code == 0
        assert "test" in result.output

    def test_main_help_includes_wp(self, cli_runner: CliRunner) -> None:
        """``astra --help`` should show the wp subcommand."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "wp" in result.output
