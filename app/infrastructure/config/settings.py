"""Application settings loaded from environment variables and .env files.

Uses ``pydantic-settings`` so that every setting is validated at startup and
documented with a type and a default value.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.constants import DEFAULT_LOG_LEVEL
from app.shared.types import Environment


class AppSettings(BaseSettings):
    """Root application settings.

    Values are loaded from environment variables prefixed with ``ASTRA_`` and
    from a ``.env`` file in the project root when present.
    """

    model_config = SettingsConfigDict(
        env_prefix="ASTRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────────────────────
    env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = DEFAULT_LOG_LEVEL

    # ── Paths ────────────────────────────────────────────────────────────
    base_dir: Path = Path.cwd()

    @property
    def is_production(self) -> bool:
        """Return ``True`` when running in production mode."""
        return self.env == Environment.PRODUCTION

    @property
    def is_debug(self) -> bool:
        """Return ``True`` when debug mode is enabled."""
        return self.debug


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return a cached singleton instance of :class:`AppSettings`.

    The first call reads from the environment; subsequent calls return the
    same object without re-parsing.
    """
    return AppSettings()
