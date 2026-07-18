"""Shared pytest fixtures for the Astra CMS test suite."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from typer.testing import CliRunner

from app.presentation.cli.main import cli


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture()
def invoke(cli_runner: CliRunner) -> Callable[..., Any]:
    """Return a convenience callable that invokes the CLI.

    Usage::

        def test_something(invoke):
            result = invoke("version")
            assert result.exit_code == 0
    """

    def _invoke(*args: str) -> object:
        return cli_runner.invoke(cli, list(args))

    return _invoke
