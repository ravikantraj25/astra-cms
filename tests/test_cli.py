"""Tests for the Typer CLI commands."""

from __future__ import annotations

from typer.testing import CliRunner

from app import __version__
from app.presentation.cli.main import cli
from app.shared.constants import APP_NAME


class TestVersionCommand:
    """Tests for ``astra version``."""

    def test_version_displays_app_name(self, cli_runner: CliRunner) -> None:
        """The version command should include the application name."""
        result = cli_runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert APP_NAME in result.output

    def test_version_displays_version_number(self, cli_runner: CliRunner) -> None:
        """The version command should include the semver string."""
        result = cli_runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_short_flag(self, cli_runner: CliRunner) -> None:
        """``--short`` should print only the bare version number."""
        result = cli_runner.invoke(cli, ["version", "--short"])
        assert result.exit_code == 0
        assert result.output.strip() == __version__


class TestDoctorCommand:
    """Tests for ``astra doctor``."""

    def test_doctor_exits_successfully(self, cli_runner: CliRunner) -> None:
        """The doctor command should always exit with code 0."""
        result = cli_runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_checks_python(self, cli_runner: CliRunner) -> None:
        """The doctor output should include a Python version check."""
        result = cli_runner.invoke(cli, ["doctor"])
        assert "Python version" in result.output

    def test_doctor_checks_packages(self, cli_runner: CliRunner) -> None:
        """The doctor output should check for core packages."""
        result = cli_runner.invoke(cli, ["doctor"])
        assert "typer" in result.output
        assert "pydantic" in result.output


class TestCliHelp:
    """Tests for the root ``--help`` behaviour."""

    def test_help_exits_successfully(self, cli_runner: CliRunner) -> None:
        """``astra --help`` should return exit code 0."""
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_help_shows_commands(self, cli_runner: CliRunner) -> None:
        """Help output should list available commands."""
        result = cli_runner.invoke(cli, ["--help"])
        assert "version" in result.output
        assert "doctor" in result.output
