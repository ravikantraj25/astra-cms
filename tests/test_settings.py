"""Tests for application settings."""

from __future__ import annotations

from app.infrastructure.config.settings import AppSettings
from app.shared.types import Environment


class TestAppSettings:
    """Tests for :class:`AppSettings`."""

    def test_default_environment(self) -> None:
        """Default environment should be development."""
        settings = AppSettings()
        assert settings.env == Environment.DEVELOPMENT

    def test_default_debug_is_false(self) -> None:
        """Debug mode should be off by default."""
        settings = AppSettings()
        assert settings.debug is False

    def test_is_production(self) -> None:
        """``is_production`` should reflect the environment."""
        settings = AppSettings(env=Environment.PRODUCTION)
        assert settings.is_production is True

    def test_is_not_production(self) -> None:
        """``is_production`` should be False for non-production environments."""
        settings = AppSettings(env=Environment.DEVELOPMENT)
        assert settings.is_production is False
