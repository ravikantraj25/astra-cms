"""Tests for the ``astra analyze`` CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_analyze_html_success(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should parse and analyze the file, outputting sections."""
    file_path = tmp_path / "post_analyze.html"
    file_path.write_text("<h2>Conclusion</h2><p>End.</p>", encoding="utf-8")

    result = cli_runner.invoke(cli, ["analyze", str(file_path)])

    assert result.exit_code == 0
    assert "Analyzed" in result.output
    assert "Conclusion" in result.output


def test_analyze_html_not_found(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should return an error if the file does not exist."""
    file_path = tmp_path / "does_not_exist.html"

    result = cli_runner.invoke(cli, ["analyze", str(file_path)])

    assert result.exit_code == 2
    assert "does_not_exist.html" in result.output
