"""Application settings loaded from environment variables and .env files.

Uses ``pydantic-settings`` so that every setting is validated at startup and
documented with a type and a default value.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.constants import DEFAULT_LOG_LEVEL
from app.shared.types import Environment


class WordPressSettings(BaseSettings):
    """WordPress connection settings.

    Loaded from environment variables prefixed with ``WP_``.
    The application password should be stored as a secret.

    ``base_url`` is validated as an HTTP(S) URL when set.
    """

    model_config = SettingsConfigDict(
        env_prefix="WP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    base_url: str = ""
    username: str = ""
    app_password: SecretStr = SecretStr("")
    timeout_connect: float = 10.0
    timeout_read: float = 30.0
    verify_ssl: bool = True

    @model_validator(mode="after")
    def _validate_base_url(self) -> WordPressSettings:
        """Validate that ``base_url`` is a proper HTTP(S) URL when provided."""
        if self.base_url:
            # Let Pydantic's HttpUrl do the heavy lifting
            parsed = HttpUrl(self.base_url)
            # Normalise: strip trailing slashes
            self.base_url = str(parsed).rstrip("/")
        return self

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when all required WordPress fields are set."""
        return bool(self.base_url and self.username and self.app_password.get_secret_value())


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


@lru_cache(maxsize=1)
def get_wp_settings() -> WordPressSettings:
    """Return a cached singleton instance of :class:`WordPressSettings`.

    The first call reads from the environment; subsequent calls return the
    same object without re-parsing.
    """
    return WordPressSettings()


class GroqSettings(BaseSettings):
    """Groq API settings.

    Loaded from environment variables prefixed with ``GROQ_``.
    """

    model_config = SettingsConfigDict(
        env_prefix="GROQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_key: SecretStr = SecretStr("")
    model: str = "llama3-8b-8192"
    base_url: str = "https://api.groq.com/openai/v1"

    @property
    def is_configured(self) -> bool:
        """Return ``True`` when API key is set."""
        return bool(self.api_key.get_secret_value())


@lru_cache(maxsize=1)
def get_groq_settings() -> GroqSettings:
    """Return a cached singleton instance of :class:`GroqSettings`."""
    return GroqSettings()
