"""Tests for the ``astra auto update`` CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from app.domain.batch import BatchSummaryReport, PostBatchResult
from app.infrastructure.config.settings import AppSettings, GroqSettings, WordPressSettings
from app.presentation.cli.main import cli

runner = CliRunner()


@pytest.fixture
def mock_wp_settings() -> WordPressSettings:
    """Return configured mock WordPressSettings."""
    return WordPressSettings(
        base_url="https://example.com",
        username="admin",
        app_password=SecretStr("secret"),
    )


@pytest.fixture
def mock_groq_settings() -> GroqSettings:
    """Return configured mock GroqSettings."""
    return GroqSettings(
        api_key=SecretStr("gsk_test"),
        model="test-model",
    )


@patch("app.presentation.cli.auto_commands.run_batch_workflow")
def test_auto_update_cli_success(
    mock_run_batch: MagicMock,
    mock_wp_settings: WordPressSettings,
    mock_groq_settings: GroqSettings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful run of astra auto update."""
    monkeypatch.chdir(tmp_path)
    mock_settings = AppSettings(base_dir=tmp_path)

    report = BatchSummaryReport(
        total_posts=2,
        successful=1,
        failed=1,
        skipped=0,
        draft_urls=["https://example.com/?p=101"],
        results=[
            PostBatchResult(
                post_id=101,
                title="Success Post",
                status="success",
                draft_url="https://example.com/?p=101",
            ),
            PostBatchResult(
                post_id=102,
                title="Failed Post",
                status="failed",
                error_message="Timeout",
            ),
        ],
    )
    mock_run_batch.return_value = report

    with (
        patch(
            "app.presentation.cli.auto_commands.get_wp_settings",
            return_value=mock_wp_settings,
        ),
        patch(
            "app.presentation.cli.auto_commands.get_groq_settings",
            return_value=mock_groq_settings,
        ),
        patch(
            "app.presentation.cli.auto_commands.get_settings",
            return_value=mock_settings,
        ),
        patch("app.presentation.cli.auto_commands.WordPressClient"),
    ):
        result = runner.invoke(cli, ["auto", "update", "--limit", "5", "--dry-run"])

    assert result.exit_code == 0, f"Output: {result.output}\nException: {result.exception}"
    assert "Batch Processing Finished!" in result.output
    assert "Total Candidates" in result.output
    assert "Generated Draft URLs:" in result.output
    assert "https://example.com/?p=101" in result.output
    assert mock_run_batch.called
    kwargs = mock_run_batch.call_args.kwargs
    assert kwargs["limit"] == 5
    assert kwargs["dry_run"] is True


def test_auto_update_cli_unconfigured() -> None:
    """Test that astra auto update exits if credentials are not set."""
    unconfigured_wp = WordPressSettings()
    with patch(
        "app.presentation.cli.auto_commands.get_wp_settings",
        return_value=unconfigured_wp,
    ):
        result = runner.invoke(cli, ["auto", "update"])

    assert result.exit_code == 1
    assert "WordPress credentials are not configured" in result.output
