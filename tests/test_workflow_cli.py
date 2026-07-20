"""Tests for the Workflow Engine CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from app.infrastructure.config.settings import GroqSettings, WordPressSettings
from app.presentation.cli.main import cli

runner = CliRunner()


@pytest.fixture
def mock_wp_settings() -> WordPressSettings:
    """Provide a mock WordPressSettings instance."""
    return WordPressSettings(
        base_url="https://example.com",
        username="admin",
        app_password=SecretStr("password"),
    )


@pytest.fixture
def mock_groq_settings() -> GroqSettings:
    """Provide a mock GroqSettings instance."""
    return GroqSettings(api_key=SecretStr("mock_key"))


@patch("app.presentation.cli.workflow_commands.run_analysis_workflow")
def test_workflow_analyze_success(
    mock_run_workflow: MagicMock,
    mock_wp_settings: WordPressSettings,
    mock_groq_settings: GroqSettings,
    tmp_path: Path,
) -> None:
    """Test the workflow analyze CLI command on a successful run."""
    mock_run_workflow.return_value = {
        "html": tmp_path / "post_123.html",
        "plan": tmp_path / "update_plan.json",
    }

    with (
        patch(
            "app.presentation.cli.workflow_commands.get_wp_settings", return_value=mock_wp_settings
        ),
        patch(
            "app.presentation.cli.workflow_commands.get_groq_settings",
            return_value=mock_groq_settings,
        ),
        patch(
            "app.infrastructure.wordpress.client.WordPressClient.__enter__",
            return_value=MagicMock()
        )
    ):
        result = runner.invoke(cli, ["workflow", "analyze", "123"])

    assert result.exit_code == 0
    assert "Executing analysis workflow for Post ID: 123" in result.output
    assert "Workflow Finished!" in result.output
    assert "Html" in result.output
    assert "Plan" in result.output


def test_workflow_analyze_missing_wp_creds(
    mock_groq_settings: GroqSettings,
) -> None:
    """Test the workflow analyze command when WP creds are missing."""
    with (
        patch(
            "app.infrastructure.config.settings.WordPressSettings.is_configured",
            new_callable=PropertyMock,
            return_value=False,
        ),
        patch(
            "app.presentation.cli.workflow_commands.get_groq_settings",
            return_value=mock_groq_settings,
        ),
    ):
        result = runner.invoke(cli, ["workflow", "analyze", "123"])

    assert result.exit_code == 1
    assert "WordPress credentials are not configured" in result.output


def test_workflow_analyze_missing_groq_creds(
    mock_wp_settings: WordPressSettings,
) -> None:
    """Test the workflow analyze command when Groq creds are missing."""
    with (
        patch(
            "app.presentation.cli.workflow_commands.get_wp_settings", return_value=mock_wp_settings
        ),
        patch(
            "app.infrastructure.config.settings.GroqSettings.is_configured",
            new_callable=PropertyMock,
            return_value=False,
        ),
    ):
        result = runner.invoke(cli, ["workflow", "analyze", "123"])

    assert result.exit_code == 1
    assert "Groq API credentials are not configured" in result.output


@patch("app.presentation.cli.workflow_commands.run_analysis_workflow")
def test_workflow_analyze_failure(
    mock_run_workflow: MagicMock,
    mock_wp_settings: WordPressSettings,
    mock_groq_settings: GroqSettings,
) -> None:
    """Test the workflow analyze CLI command when the workflow fails."""
    mock_run_workflow.side_effect = RuntimeError("Something bad happened.")

    with (
        patch(
            "app.presentation.cli.workflow_commands.get_wp_settings", return_value=mock_wp_settings
        ),
        patch(
            "app.presentation.cli.workflow_commands.get_groq_settings",
            return_value=mock_groq_settings,
        ),
        patch(
            "app.infrastructure.wordpress.client.WordPressClient.__enter__",
            return_value=MagicMock()
        )
    ):
        result = runner.invoke(cli, ["workflow", "analyze", "123"])

    assert result.exit_code == 1
    assert "Workflow Failed: Something bad happened" in result.output


@patch("app.presentation.cli.workflow_commands.generate_updated_article")
def test_workflow_generate_success(
    mock_gen: MagicMock,
    mock_groq_settings: GroqSettings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful run of workflow generate."""
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    article_file = output_dir / "post_123.html"
    article_file.write_text("<h1>Title</h1><p>Old</p>", encoding="utf-8")

    plan_file = output_dir / "update_plan.json"
    plan_file.write_text('{"actions": []}', encoding="utf-8")

    from app.domain.plan import UpdateReport

    report = UpdateReport(updated_sections=["Intro"], confidence_score=95.0)
    mock_gen.return_value = ("<h1>Title</h1><p>New</p>", report)

    from app.infrastructure.config.settings import AppSettings

    mock_settings = AppSettings(base_dir=tmp_path)

    with (
        patch(
            "app.presentation.cli.workflow_commands.get_groq_settings",
            return_value=mock_groq_settings,
        ),
        patch(
            "app.presentation.cli.workflow_commands.get_settings",
            return_value=mock_settings,
        ),
    ):
        result = runner.invoke(cli, ["workflow", "generate", "123"])

    assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
    assert "Loaded original article" in result.output
    assert "Loaded AI analysis" in result.output
    assert "Applied update plan" in result.output
    assert "Generated updated HTML" in result.output
    assert "Saved update report" in result.output

    assert (output_dir / "post_123_updated.html").exists()
    assert (output_dir / "update_report.json").exists()


@patch("app.presentation.cli.workflow_commands.WordPressClient")
def test_workflow_publish_success(
    mock_client_cls: MagicMock,
    mock_wp_settings: WordPressSettings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful run of workflow publish."""
    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    updated_file = output_dir / "post_123_updated.html"
    updated_file.write_text("<h1>Title</h1><p>Draft</p>", encoding="utf-8")

    original_file = output_dir / "post_123.html"
    original_file.write_text("<h1>Old Title</h1><p>Old Draft</p>", encoding="utf-8")

    from app.infrastructure.config.settings import AppSettings
    from app.infrastructure.wordpress.models import WPPost

    mock_settings = AppSettings(base_dir=tmp_path)
    mock_client = mock_client_cls.return_value
    mock_client.__enter__.return_value = mock_client
    mock_client.update_post.return_value = WPPost(
        id=123,
        title="Title",
        status="draft",
        link="https://example.com/?p=123",
        content_html="<h1>Title</h1><p>Draft</p>",
    )

    with (
        patch(
            "app.presentation.cli.workflow_commands.get_wp_settings",
            return_value=mock_wp_settings,
        ),
        patch(
            "app.presentation.cli.workflow_commands.get_settings",
            return_value=mock_settings,
        ),
    ):
        result = runner.invoke(cli, ["workflow", "publish", "123"])

    assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
    assert "Connected" in result.output
    assert "Loaded updated HTML" in result.output
    assert "Uploaded draft" in result.output
    assert "Draft URL:" in result.output
    assert "https://example.com/?p=123" in result.output


def test_workflow_publish_missing_file(
    mock_wp_settings: WordPressSettings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test workflow publish when updated HTML file does not exist."""
    monkeypatch.chdir(tmp_path)
    from app.infrastructure.config.settings import AppSettings

    mock_settings = AppSettings(base_dir=tmp_path)

    with (
        patch(
            "app.presentation.cli.workflow_commands.get_wp_settings",
            return_value=mock_wp_settings,
        ),
        patch(
            "app.presentation.cli.workflow_commands.get_settings",
            return_value=mock_settings,
        ),
    ):
        result = runner.invoke(cli, ["workflow", "publish", "123"])

    assert result.exit_code == 1
    assert "Updated HTML file not found" in result.output
