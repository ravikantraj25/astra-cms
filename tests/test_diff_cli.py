"""Tests for the ``astra diff`` CLI command."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_diff_articles_success(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should compare two HTML files and generate update_diff.json."""
    monkeypatch.chdir(tmp_path)

    original_file = tmp_path / "post_123.html"
    original_file.write_text("<h1>Title</h1><p>Original text.</p>", encoding="utf-8")

    updated_file = tmp_path / "post_123_ai.html"
    updated_file.write_text("<h1>Title</h1><p>Updated text.</p>", encoding="utf-8")

    result = cli_runner.invoke(cli, ["diff", str(original_file), str(updated_file)])

    assert result.exit_code == 0
    assert "Compared" in result.output
    assert "Modified" in result.output

    diff_file = tmp_path / "update_diff.json"
    assert diff_file.exists()

    diff_data = json.loads(diff_file.read_text(encoding="utf-8"))
    assert "added" in diff_data
    assert "removed" in diff_data
    assert "modified" in diff_data
    assert len(diff_data["modified"]) == 1


def test_diff_articles_file_not_found(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should fail gracefully if files are not found."""
    monkeypatch.chdir(tmp_path)

    # Original missing
    result = cli_runner.invoke(cli, ["diff", "missing.html", "other.html"])
    assert result.exit_code == 2  # Typer argument validation failure for exists=True
