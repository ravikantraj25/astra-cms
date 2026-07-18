"""Tests for the ``astra prompt`` CLI command."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_generate_prompt_success(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should generate a prompt and save it to the output directory."""
    # Change to tmp_path so "output/prompt.txt" is written safely
    monkeypatch.chdir(tmp_path)

    # Create a dummy HTML file
    file_path = tmp_path / "post_prompt.html"
    file_path.write_text(
        "<h1>Test Title</h1><h2>Introduction</h2><p>Content.</p>", encoding="utf-8"
    )

    result = cli_runner.invoke(cli, ["prompt", str(file_path)])

    assert result.exit_code == 0
    assert "Prompt Generated" in result.output
    assert "Test Title" in result.output

    prompt_file = tmp_path / "output" / "prompt.txt"
    assert prompt_file.exists()

    prompt_text = prompt_file.read_text(encoding="utf-8")
    assert "ARTICLE UPDATE PROMPT" in prompt_text
    assert "Title: Test Title" in prompt_text


def test_generate_prompt_not_found(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should return an error if the file does not exist."""
    file_path = tmp_path / "does_not_exist.html"

    result = cli_runner.invoke(cli, ["prompt", str(file_path)])

    assert result.exit_code == 2
    assert "does_not_exist.html" in result.output
