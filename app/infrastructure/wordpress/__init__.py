"""WordPress REST API client and data adapters.

Public API::

    from app.infrastructure.wordpress import WordPressClient
    from app.infrastructure.wordpress.exceptions import AuthenticationError
    from app.infrastructure.wordpress.models import WPSiteInfo, WPUser, WPPost
"""

from app.infrastructure.wordpress.client import WordPressClient
from app.infrastructure.wordpress.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    RateLimitError,
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import (
    WPHealthCheck,
    WPPost,
    WPPostDetail,
    WPPostList,
    WPSiteInfo,
    WPUser,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "ConnectionError",
    "RateLimitError",
    "TimeoutError",
    "WPHealthCheck",
    "WPPost",
    "WPPostDetail",
    "WPPostList",
    "WPSiteInfo",
    "WPUser",
    "WordPressClient",
    "WordPressError",
]
