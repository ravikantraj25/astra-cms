"""Structured logging setup for Astra CMS.

Provides a pre-configured :func:`get_logger` factory that returns stdlib
loggers with consistent formatting and a :class:`LogContext` dataclass for
passing contextual metadata through log calls.

Architecture notes:
    The :class:`LogContext` prepares the codebase for future structured
    logging (e.g. ``structlog``) without changing existing behaviour.
    Every log call *can* include ``module``, ``job_id``, ``post_id``,
    and ``elapsed_time`` via the ``extra`` dict — today these are rendered
    into the plain-text format; tomorrow they will become first-class
    structured fields.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import asdict, dataclass
from typing import Any, Final

from app.shared.constants import APP_SLUG, DEFAULT_LOG_LEVEL

_LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s" "%(log_context)s"
)
_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

_configured: bool = False


# ── Contextual Metadata ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LogContext:
    """Structured metadata that can accompany any log message.

    Pass an instance to :meth:`AstraLogger.info`, etc. via the ``ctx``
    parameter.  Fields with ``None`` values are omitted from the output.

    Attributes:
        module: The logical module emitting the log (e.g. ``"wordpress"``).
        job_id: An optional job/task identifier for batch operations.
        post_id: An optional WordPress post ID for per-post operations.
        elapsed_time: Duration in seconds for timed operations.
    """

    module: str | None = None
    job_id: str | None = None
    post_id: int | None = None
    elapsed_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a dict of non-None fields for use in log ``extra``."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def format(self) -> str:
        """Return a human-readable suffix for plain-text log lines."""
        parts = self.to_dict()
        if not parts:
            return ""
        formatted = " | ".join(f"{k}={v}" for k, v in parts.items())
        return f" | {formatted}"


# ── Custom Filter ────────────────────────────────────────────────────────────


class _ContextFilter(logging.Filter):
    """Inject ``log_context`` into every log record.

    If the caller did not supply a ``log_context`` extra field, an empty
    string is used so the formatter never raises a ``KeyError``.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "log_context"):
            record.log_context = ""  # type: ignore[attr-defined]
        return True


# ── Setup ────────────────────────────────────────────────────────────────────


def setup_logging(level: str = DEFAULT_LOG_LEVEL) -> None:
    """Configure the root logger for the application.

    Safe to call multiple times — subsequent calls are no-ops.

    Args:
        level: The logging level name (e.g. ``"DEBUG"``, ``"INFO"``).
    """
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    handler.addFilter(_ContextFilter())

    root = logging.getLogger(APP_SLUG)
    root.setLevel(numeric_level)
    root.addHandler(handler)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger scoped under the application namespace.

    Usage::

        logger = get_logger("wordpress.client")
        logger.info("Fetched posts", extra={"log_context": ctx.format()})

    Args:
        name: Dot-separated logger name (e.g. ``"cli.commands"``).

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(f"{APP_SLUG}.{name}")
