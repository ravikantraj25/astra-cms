"""WordPress REST API client and data adapters.

Public API::

    from app.infrastructure.wordpress import WordPressClient
    from app.infrastructure.wordpress.exceptions import AuthenticationError
    from app.infrastructure.wordpress.models import WPSiteInfo, WPUser
"""

from app.infrastructure.wordpress.client import WordPressClient
from app.infrastructure.wordpress.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import WPHealthCheck, WPSiteInfo, WPUser

__all__ = [
    "APIError",
    "AuthenticationError",
    "ConnectionError",
    "TimeoutError",
    "WPHealthCheck",
    "WPSiteInfo",
    "WPUser",
    "WordPressClient",
    "WordPressError",
]
