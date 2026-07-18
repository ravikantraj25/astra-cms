"""Structured logging setup for Astra CMS.

Provides a pre-configured :func:`get_logger` factory that returns stdlib
loggers with consistent formatting.  A future iteration may swap in
``structlog`` or another backend without changing call-sites.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

from app.shared.constants import APP_SLUG, DEFAULT_LOG_LEVEL

_LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

_configured: bool = False


def setup_logging(level: str = DEFAULT_LOG_LEVEL) -> None:
    """Configure the root logger for the application.

    Safe to call multiple times — subsequent calls are no-ops.

    Args:
        level: The logging level name (e.g. ``"DEBUG"``, ``"INFO"``).
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger(APP_SLUG)
    root.setLevel(numeric_level)
    root.addHandler(handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger scoped under the application namespace.

    Args:
        name: Dot-separated logger name (e.g. ``"cli.commands"``).

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(f"{APP_SLUG}.{name}")
