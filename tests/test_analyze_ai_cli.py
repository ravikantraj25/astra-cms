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


from app.domain.intelligence import ArticleAnalysis, ArticleType, ContentFreshness, UpdateStrategy, EditingPolicy, PolicyAction

@pytest.fixture
def dummy_intelligence():
    return ArticleAnalysis(
        strategy=UpdateStrategy.SELECTIVE,
        freshness=ContentFreshness.RECURRING_EVENT,
        editing_policy=EditingPolicy(
            article_type=ArticleType.ANNUAL_EVENT,
            year_policy=PolicyAction.UPDATE,
            date_policy=PolicyAction.UPDATE,
            history_policy=PolicyAction.KEEP,
            title_policy=PolicyAction.UPDATE,
            image_policy=PolicyAction.KEEP,
            schema_policy=PolicyAction.KEEP,
            faq_policy=PolicyAction.UPDATE,
            schedule_policy=PolicyAction.UPDATE,
            pricing_policy=PolicyAction.UPDATE,
            metadata_policy=PolicyAction.UPDATE,
            link_policy=PolicyAction.KEEP,
            location_policy=PolicyAction.KEEP,
            seo_policy=PolicyAction.UPDATE
        ),
        required_updates=[],
        forbidden_updates=[],
        temporal_entities=[],
        historical_facts=[],
        event_info=[],
        structural_analysis=[],
        risks=[],
    )

@patch("app.presentation.cli.main.ContentIntelligenceAnalyzer")
def test_analyze_ai_success(
    mock_analyzer_cls: MagicMock,
    cli_runner: CliRunner, 
    tmp_path: Path, 
    monkeypatch: pytest.MonkeyPatch,
    dummy_intelligence: ArticleAnalysis
) -> None:
    """It should call GroqProvider and save JSON output."""
    monkeypatch.chdir(tmp_path)

    file_path = tmp_path / "post_test.html"
    file_path.write_text("<h1>Test</h1>", encoding="utf-8")

    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.analyze.return_value = dummy_intelligence
    mock_analyzer_cls.return_value = mock_analyzer_instance

    with (
        patch("app.infrastructure.config.settings.get_groq_settings") as mock_settings,
        patch("app.infrastructure.providers.groq_provider.GroqProvider") as MockProvider,
    ):
        mock_settings.return_value = MagicMock(is_configured=True)

        result = cli_runner.invoke(cli, ["analyze-ai", str(file_path)])

        assert result.exit_code == 0
        assert "Success" in result.output

        output_file = tmp_path / "output" / "analysis.json"
        assert output_file.exists()

        saved_json = json.loads(output_file.read_text(encoding="utf-8"))
        assert saved_json["strategy"] == "Selective"


def test_analyze_ai_not_configured(cli_runner: CliRunner, tmp_path: Path) -> None:
    """It should error if Groq is not configured."""
    file_path = tmp_path / "post_test.html"
    file_path.write_text("<h1>Test</h1>", encoding="utf-8")

    with patch("app.infrastructure.config.settings.get_groq_settings") as mock_settings:
        mock_settings.return_value = MagicMock(is_configured=False)

        result = cli_runner.invoke(cli, ["analyze-ai", str(file_path)])

        assert result.exit_code == 1
        assert "not configured" in result.output
