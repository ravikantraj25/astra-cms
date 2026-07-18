"""Application-wide constants.

All magic strings and default values live here so they can be changed in one place.
"""

from typing import Final

# ── Application Metadata ─────────────────────────────────────────────────────

APP_NAME: Final[str] = "Astra CMS"
APP_SLUG: Final[str] = "astra-cms"
APP_DESCRIPTION: Final[str] = (
    "A modern, AI-powered headless CMS migration and management toolkit."
)

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
DEFAULT_ENCODING: Final[str] = "utf-8"

# ── Paths (relative to project root) ─────────────────────────────────────────

LOGS_DIR: Final[str] = "logs"
BACKUPS_DIR: Final[str] = "backups"
OUTPUT_DIR: Final[str] = "output"
DATA_DIR: Final[str] = "data"
CONFIG_DIR: Final[str] = "config"
