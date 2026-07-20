"""Tests for the ``astra plan`` CLI command."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_generate_plan_success_single_html(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should generate a plan successfully when there is exactly one HTML file."""
    monkeypatch.chdir(tmp_path)

    html_file = tmp_path / "post_123.html"
    html_file.write_text("<h1>Test</h1><h2>FAQ</h2>", encoding="utf-8")

    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps({
        "strengths": [],
        "weaknesses": ["outdated info"],
        "suggestions": ["update faq"],
        "confidence_scores": {"FAQ": 95}
    }), encoding="utf-8")

    result = cli_runner.invoke(cli, ["plan", str(analysis_file)])

    assert result.exit_code == 0
    assert "Generated Plan for" in result.output

    plan_file = tmp_path / "update_plan.json"
    assert plan_file.exists()

    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
    assert "actions" in plan_data


def test_generate_plan_multiple_html_requires_article(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should require the --article flag if multiple HTML files exist."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / "post_1.html").write_text("<h1>1</h1>", encoding="utf-8")
    (tmp_path / "post_2.html").write_text("<h1>2</h1>", encoding="utf-8")

    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps({}), encoding="utf-8")

    result = cli_runner.invoke(cli, ["plan", str(analysis_file)])

    assert result.exit_code == 1
    assert "Multiple HTML files found" in result.output
