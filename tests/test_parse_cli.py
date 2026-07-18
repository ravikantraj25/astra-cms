"""Tests for the ``astra parse`` CLI command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_parse_html_success(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should parse the file and output a summary table."""
    file_path = tmp_path / "post_123.html"
    file_path.write_text("<h1>Test Post</h1><p>Word count.</p>", encoding="utf-8")

    result = cli_runner.invoke(cli, ["parse", str(file_path)])

    assert result.exit_code == 0
    assert "Parsed" in result.output
    assert "Test Post" in result.output
    assert "Word count" in result.output
    assert "Images" in result.output


def test_parse_html_not_found(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should return an error if the file does not exist."""
    file_path = tmp_path / "does_not_exist.html"

    result = cli_runner.invoke(cli, ["parse", str(file_path)])

    assert result.exit_code == 2
    assert "does_not_exist.html" in result.output
