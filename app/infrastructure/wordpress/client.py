"""WordPress REST API client using httpx.

Provides a high-level, async-capable client that authenticates via
WordPress Application Passwords and exposes connection-testing methods.

Usage::

    from app.infrastructure.wordpress.client import WordPressClient

    client = WordPressClient(base_url="https://example.com", username="admin", app_password="xxxx")
    health = client.health_check()
    print(health.site_info.name)
"""

from __future__ import annotations

import httpx

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.wordpress.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import WPHealthCheck, WPSiteInfo, WPUser

logger = get_logger("wordpress.client")

# WordPress REST API base path
_WP_JSON_PATH: str = "/wp-json"
_WP_V2_PATH: str = f"{_WP_JSON_PATH}/wp/v2"

# Default timeouts (seconds)
_DEFAULT_CONNECT_TIMEOUT: float = 10.0
_DEFAULT_READ_TIMEOUT: float = 30.0


class WordPressClient:
    """HTTP client for the WordPress REST API.

    Uses HTTP Basic Auth with Application Passwords (introduced in WP 5.6).
    All network errors are translated into domain-specific exceptions from
    :mod:`app.infrastructure.wordpress.exceptions`.

    Args:
        base_url: The root URL of the WordPress site (e.g. ``https://example.com``).
        username: WordPress username.
        app_password: A WordPress Application Password (not the account password).
        timeout: Optional tuple of (connect_timeout, read_timeout) in seconds.
        verify_ssl: Whether to verify SSL certificates. Defaults to ``True``.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        app_password: str,
        timeout: tuple[float, float] | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._app_password = app_password
        self._verify_ssl = verify_ssl

        connect_t, read_t = timeout or (_DEFAULT_CONNECT_TIMEOUT, _DEFAULT_READ_TIMEOUT)
        self._timeout = httpx.Timeout(connect=connect_t, read=read_t, write=read_t, pool=read_t)

        self._client: httpx.Client | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Create the underlying HTTP client and verify connectivity.

        Raises:
            ConnectionError: If the WordPress site is unreachable.
            AuthenticationError: If the credentials are invalid.
        """
        logger.info("Connecting to WordPress at %s", self._base_url)
        self._client = httpx.Client(
            base_url=self._base_url,
            auth=(self._username, self._app_password),
            timeout=self._timeout,
            verify=self._verify_ssl,
            headers={"User-Agent": "AstraCMS/0.1.0"},
        )

        # Quick connectivity probe — hit the root REST endpoint
        self._request("GET", _WP_JSON_PATH)
        logger.info("Connected successfully to %s", self._base_url)

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> WordPressClient:
        """Support ``with`` statement for automatic resource management."""
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        """Close the client when exiting the ``with`` block."""
        self.close()

    # ── Public API ───────────────────────────────────────────────────────────

    def get_site_info(self) -> WPSiteInfo:
        """Fetch site metadata from the WordPress REST API root.

        Returns:
            A :class:`WPSiteInfo` containing the site name, URL, and available
            REST namespaces.

        Raises:
            WordPressError: On any API or network failure.
        """
        data = self._request("GET", _WP_JSON_PATH)
        return WPSiteInfo.model_validate(data)

    def get_current_user(self) -> WPUser:
        """Fetch the currently authenticated user.

        Returns:
            A :class:`WPUser` with the user's display name, roles, and ID.

        Raises:
            AuthenticationError: If the credentials are invalid.
            WordPressError: On any other API failure.
        """
        data = self._request("GET", f"{_WP_V2_PATH}/users/me", params={"context": "edit"})
        return WPUser.model_validate(data)

    def health_check(self) -> WPHealthCheck:
        """Run a comprehensive connection health check.

        Fetches site info, current user, and determines the WordPress version.

        Returns:
            A :class:`WPHealthCheck` aggregating all connection diagnostics.

        Raises:
            WordPressError: On any API or network failure.
        """
        site_info = self.get_site_info()
        current_user = self.get_current_user()

        # WordPress exposes its version in the wp/v2 namespace discovery
        wp_version = self._detect_wp_version()

        return WPHealthCheck(
            site_info=site_info,
            current_user=current_user,
            wp_version=wp_version,
            rest_api_healthy=True,
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _ensure_connected(self) -> httpx.Client:
        """Return the active httpx client or raise if not connected."""
        if self._client is None:
            msg = "Client is not connected. Call connect() first."
            raise WordPressError(msg)
        return self._client

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        """Execute an HTTP request and translate errors to domain exceptions.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path relative to base_url.
            params: Optional query parameters.

        Returns:
            The parsed JSON response as a dictionary.

        Raises:
            AuthenticationError: On 401/403 responses.
            APIError: On other non-2xx responses.
            ConnectionError: On network-level failures.
            TimeoutError: When the request times out.
        """
        client = self._ensure_connected()

        try:
            response = client.request(method, path, params=params)
        except httpx.TimeoutException as exc:
            logger.error("Request timed out: %s %s", method, path)
            raise TimeoutError(
                message=f"Request timed out: {method} {path}",
            ) from exc
        except httpx.ConnectError as exc:
            logger.error("Connection failed: %s", exc)
            raise ConnectionError(
                message=f"Could not connect to {self._base_url}: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("HTTP error: %s", exc)
            raise ConnectionError(
                message=f"Network error: {exc}",
            ) from exc

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict[str, object]:
        """Validate the HTTP response and return parsed JSON.

        Args:
            response: The httpx response object.

        Returns:
            Parsed JSON dictionary.

        Raises:
            AuthenticationError: On 401/403.
            APIError: On other error status codes.
        """
        if response.status_code in (401, 403):
            logger.warning("Authentication failed (HTTP %d)", response.status_code)
            msg = self._extract_error_message(response)
            raise AuthenticationError(
                message=f"Authentication failed (HTTP {response.status_code}): {msg}",
            )

        if response.status_code >= 400:  # noqa: PLR2004
            logger.warning("API error (HTTP %d)", response.status_code)
            msg = self._extract_error_message(response)
            raise APIError(
                message=f"WordPress API error (HTTP {response.status_code}): {msg}",
                status_code=response.status_code,
            )

        try:
            data: dict[str, object] = response.json()
        except Exception as exc:
            raise APIError(
                message="Failed to parse WordPress JSON response.",
                status_code=response.status_code,
            ) from exc

        return data

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract a human-readable error from a WordPress error response."""
        try:
            body = response.json()
            if isinstance(body, dict):
                return str(body.get("message", response.reason_phrase))
        except Exception:  # noqa: BLE001
            pass
        return response.reason_phrase or "Unknown error"

    def _detect_wp_version(self) -> str:
        """Attempt to detect the WordPress version.

        The version is not always exposed in the REST API for security
        reasons.  Falls back to ``"unknown"`` when it cannot be determined.
        """
        try:
            client = self._ensure_connected()
            # WordPress often includes the version in the root HTML via the generator meta tag
            # But the REST API root sometimes exposes it in the `authentication` or header
            response = client.request("GET", _WP_JSON_PATH)
            data = response.json()

            # Some WP configs expose version in the root REST response
            if isinstance(data, dict):
                # Check common locations for version info
                version = data.get("description", "")
                # The WP-Version header is sometimes available
                wp_header = response.headers.get("x-wp-version", "")
                if wp_header:
                    return wp_header

            return "unknown"
        except Exception:  # noqa: BLE001
            return "unknown"
