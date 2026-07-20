"""Tests for the ``astra generate`` CLI command."""

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


@pytest.fixture
def mock_groq_settings() -> MagicMock:
    """Mock GroqSettings."""
    settings = MagicMock()
    settings.is_configured = True
    settings.api_key = "test_key"
    settings.model_name = "test-model"
    return settings


def test_generate_html_success(
    cli_runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mock_groq_settings: MagicMock,
) -> None:
    """It should generate updated HTML based on the update plan."""
    monkeypatch.chdir(tmp_path)

    # Create dummy article
    article_html = '<h1>Title</h1>\n<p data-astra-id="1">Original Intro</p>'
    article_file = tmp_path / "post_123.html"
    article_file.write_text(article_html, encoding="utf-8")

    # Create dummy plan
    plan_data = {
        "actions": [
            {
                "section": "Introduction",
                "reason": "Needs SEO",
                "priority": "High",
                "confidence": 90,
                "action": "Update",
            }
        ]
    }
    plan_file = tmp_path / "update_plan.json"
    plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

    with (
        patch(
            "app.infrastructure.config.settings.get_groq_settings", return_value=mock_groq_settings
        ),
        patch("app.infrastructure.providers.groq_provider.GroqProvider") as MockProvider,
        patch("app.application.section_detector.detect_sections") as mock_detect,
    ):
        mock_provider_instance = MockProvider.return_value
        mock_provider_instance.generate.return_value = "<ASTRA_HTML_START>\n<p>Updated Intro</p>\n<ASTRA_HTML_END>"

        # Mock detect_sections to return a section matching our plan
        from app.domain.article import Article, Section

        mock_article = Article(
            title="Title",
            raw_html=article_html,
            sections=[
                Section(
                    name="Introduction",
                    type="Paragraph",
                    astra_id="1",
                    content="<p>Original Intro</p>",
                )
            ],
        )
        mock_detect.return_value = mock_article

        result = cli_runner.invoke(cli, ["generate", str(plan_file)])

        assert result.exit_code == 0
        assert "Generating HTML for" in result.output
        assert "HTML Generation Complete" in result.output

        updated_file = tmp_path / "post_123_updated.html"
        assert updated_file.exists()

        content = updated_file.read_text(encoding="utf-8")
        assert content == "<h1>Title</h1>\n<p>Updated Intro</p>"


def test_generate_html_unconfigured(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It should fail if Groq API is not configured."""
    monkeypatch.chdir(tmp_path)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text("{}")

    with patch("app.infrastructure.config.settings.get_groq_settings") as mock_settings:
        mock_settings.return_value.is_configured = False

        result = cli_runner.invoke(cli, ["generate", str(plan_file)])

        assert result.exit_code == 1
        assert "Groq API key is not configured" in result.output
