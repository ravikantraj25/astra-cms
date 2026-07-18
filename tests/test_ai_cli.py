"""Tests for the ``astra ai`` CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_ai_health_not_configured(cli_runner: CliRunner) -> None:
    """It should show Not Configured if API key is missing."""
    with patch("app.presentation.cli.ai_commands.get_groq_settings") as mock_settings:
        mock_settings.return_value = MagicMock(is_configured=False, model="llama3-8b-8192")

        result = cli_runner.invoke(cli, ["ai", "health"])

        assert result.exit_code == 0
        assert "Not Configured" in result.output


def test_ai_health_connected(cli_runner: CliRunner) -> None:
    """It should show Connected if API check passes."""
    with (
        patch("app.presentation.cli.ai_commands.get_groq_settings") as mock_settings,
        patch("app.presentation.cli.ai_commands.GroqProvider") as MockProvider,
    ):
        mock_settings.return_value = MagicMock(is_configured=True, model="llama3-8b-8192")
        mock_provider_instance = MockProvider.return_value
        mock_provider_instance.http_client.get.return_value = MagicMock()

        result = cli_runner.invoke(cli, ["ai", "health"])

        assert result.exit_code == 0
        assert "Connected" in result.output
        assert "llama3-8b-8192" in result.output


def test_ai_health_connection_failed(cli_runner: CliRunner) -> None:
    """It should show Connection Failed if API check raises exception."""
    with (
        patch("app.presentation.cli.ai_commands.get_groq_settings") as mock_settings,
        patch("app.presentation.cli.ai_commands.GroqProvider") as MockProvider,
    ):
        mock_settings.return_value = MagicMock(is_configured=True, model="llama3-8b-8192")
        mock_provider_instance = MockProvider.return_value
        mock_provider_instance.http_client.get.side_effect = Exception("API error")

        result = cli_runner.invoke(cli, ["ai", "health"])

        assert result.exit_code == 0
        assert "Connection Failed" in result.output
