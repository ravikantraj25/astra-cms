"""Tests for the ``astra analyze-ai`` CLI command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_analyze_ai_success(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should call GroqProvider and save JSON output."""
    monkeypatch.chdir(tmp_path)

    file_path = tmp_path / "post_test.html"
    file_path.write_text("<h1>Test</h1>", encoding="utf-8")

    mock_json = json.dumps({
        "article_type": "Annual Event",
        "freshness": "Recurring Event",
        "decision": {
            "strategy": "Selective",
            "reason": "Because it's an annual event."
        },
        "temporal_entities": [],
        "historical_facts": [],
        "event_info": [],
        "structural_analysis": [],
        "risks": []
    })

    with (
        patch("app.infrastructure.config.settings.get_groq_settings") as mock_settings,
        patch("app.infrastructure.providers.groq_provider.GroqProvider") as MockProvider,
    ):
        mock_settings.return_value = MagicMock(is_configured=True)

        mock_provider_instance = MockProvider.return_value
        mock_provider_instance.generate.return_value = f"```json\n{mock_json}\n```"

        result = cli_runner.invoke(cli, ["analyze-ai", str(file_path)])

        assert result.exit_code == 0
        assert "Success" in result.output

        output_file = tmp_path / "output" / "analysis.json"
        assert output_file.exists()

        saved_json = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved_json["article_type"] == "Annual Event"


def test_analyze_ai_not_configured(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should error if Groq is not configured."""
    file_path = tmp_path / "post_test.html"
    file_path.write_text("<h1>Test</h1>", encoding="utf-8")

    with patch("app.infrastructure.config.settings.get_groq_settings") as mock_settings:
        mock_settings.return_value = MagicMock(is_configured=False)

        result = cli_runner.invoke(cli, ["analyze-ai", str(file_path)])

        assert result.exit_code == 1
        assert "not configured" in result.output
