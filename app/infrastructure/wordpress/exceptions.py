"""Custom exceptions for WordPress API interactions.

Each exception maps to a specific failure mode, enabling callers to handle
errors granularly without inspecting raw HTTP status codes or messages.
"""

from __future__ import annotations


class WordPressError(Exception):
    """Base exception for all WordPress-related errors.

    All other WordPress exceptions inherit from this class, so a single
    ``except WordPressError`` can catch every WordPress failure.

    Attributes:
        message: A human-readable description of the error.
        status_code: The HTTP status code returned by the WordPress API, if any.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(WordPressError):
    """Raised when WordPress rejects the provided credentials.

    Common causes:
    - Invalid application password.
    - Incorrect username.
    - Application passwords disabled on the WordPress instance.
    """

    def __init__(self, message: str = "Authentication failed. Check your credentials.") -> None:
        super().__init__(message=message, status_code=401)


class ConnectionError(WordPressError):
    """Raised when the HTTP connection to WordPress cannot be established.

    Common causes:
    - No internet connectivity.
    - DNS resolution failure.
    - SSL certificate errors.
    - Connection timeout.
    """

    def __init__(self, message: str = "Could not connect to WordPress.") -> None:
        super().__init__(message=message, status_code=None)


class TimeoutError(WordPressError):
    """Raised when a WordPress API request exceeds the configured timeout."""

    def __init__(self, message: str = "Request to WordPress timed out.") -> None:
        super().__init__(message=message, status_code=None)


class APIError(WordPressError):
    """Raised when the WordPress REST API returns an unexpected error response.

    This covers scenarios such as:
    - REST API disabled.
    - Endpoint not found (404).
    - Server errors (5xx).
    """

    def __init__(
        self,
        message: str = "WordPress REST API returned an error.",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message=message, status_code=status_code)
