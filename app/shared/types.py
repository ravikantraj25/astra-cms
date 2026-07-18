"""Shared type aliases used across the application.

Centralising type aliases here keeps domain and infrastructure layers
consistent and makes future refactors straightforward.
"""

from enum import StrEnum
from typing import Any

# Generic JSON-compatible dictionary
JsonDict = dict[str, Any]


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
