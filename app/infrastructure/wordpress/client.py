"""WordPress REST API client using httpx.

Provides a high-level client that authenticates via WordPress Application
Passwords and exposes connection-testing and content-fetching methods.

The client supports **dependency injection** of the underlying
:class:`httpx.Client`, making it easy to test without mocking internals.

Usage::

    from app.infrastructure.wordpress.client import WordPressClient

    # Default — client creates its own httpx.Client
    client = WordPressClient(
        base_url="https://example.com",
        username="admin",
        app_password="xxxx",
    )

    # DI — caller injects a pre-configured httpx.Client
    http = httpx.Client(base_url="https://example.com", auth=("admin", "xxxx"))
    client = WordPressClient(base_url="https://example.com", http_client=http)
"""

from __future__ import annotations

import httpx

from app.infrastructure.logging.logger import get_logger
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
    WPPostList,
    WPSiteInfo,
    WPUser,
)

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

    Supports **dependency injection**: pass a pre-configured ``http_client``
    to skip internal client creation, or omit it to let the class build its
    own :class:`httpx.Client` on :meth:`connect`.

    Args:
        base_url: The root URL of the WordPress site.
        username: WordPress username (ignored when ``http_client`` is provided).
        app_password: WordPress Application Password (ignored when ``http_client`` is provided).
        timeout: Optional ``(connect, read)`` tuple in seconds.
        verify_ssl: Whether to verify SSL certificates.
        http_client: An optional pre-configured :class:`httpx.Client`.
    """

    def __init__(
        self,
        base_url: str,
        username: str = "",
        app_password: str = "",
        timeout: tuple[float, float] | None = None,
        verify_ssl: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._app_password = app_password
        self._verify_ssl = verify_ssl
        self._owns_client: bool = http_client is None

        connect_t, read_t = timeout or (_DEFAULT_CONNECT_TIMEOUT, _DEFAULT_READ_TIMEOUT)
        self._timeout = httpx.Timeout(connect=connect_t, read=read_t, write=read_t, pool=read_t)

        # If an external client was injected, use it immediately
        self._client: httpx.Client | None = http_client

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Create the underlying HTTP client and verify connectivity.

        If an ``http_client`` was injected via the constructor, this method
        only performs the connectivity probe (it does not create a new client).

        Raises:
            ConnectionError: If the WordPress site is unreachable.
            AuthenticationError: If the credentials are invalid.
        """
        logger.info("Connecting to WordPress at %s", self._base_url)

        if self._client is None:
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
        """Close the underlying HTTP connection pool.

        Only closes the client if it was created internally (not injected).
        """
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    def __enter__(self) -> WordPressClient:
        """Support ``with`` statement for automatic resource management."""
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        """Close the client when exiting the ``with`` block."""
        self.close()

    # ── Public API — Connection ──────────────────────────────────────────────

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
        wp_version = self._detect_wp_version()

        return WPHealthCheck(
            site_info=site_info,
            current_user=current_user,
            wp_version=wp_version,
            rest_api_healthy=True,
        )

    # ── Public API — Posts ───────────────────────────────────────────────────

    def get_posts(
        self,
        per_page: int = 10,
        page: int = 1,
        search: str = "",
        status: str = "publish",
    ) -> WPPostList:
        """Fetch posts from the WordPress REST API.

        Args:
            per_page: Number of posts per page (1-100). Defaults to ``10``.
            page: Page number to retrieve. Defaults to ``1``.
            search: Optional search query to filter posts.
            status: Post status filter (e.g. ``"publish"``, ``"draft"``).

        Returns:
            A :class:`WPPostList` containing the posts and pagination metadata.

        Raises:
            AuthenticationError: If credentials are invalid.
            RateLimitError: If WordPress rate-limits the request (HTTP 429).
            WordPressError: On any other API or network failure.
        """
        params: dict[str, str] = {
            "per_page": str(min(max(per_page, 1), 100)),
            "page": str(max(page, 1)),
            "status": status,
            "orderby": "date",
            "order": "desc",
        }
        if search:
            params["search"] = search

        response = self._request_raw("GET", f"{_WP_V2_PATH}/posts", params=params)

        # Parse pagination headers
        total = int(response.headers.get("X-WP-Total", "0"))
        total_pages = int(response.headers.get("X-WP-TotalPages", "0"))

        raw_posts = self._parse_json(response)
        if not isinstance(raw_posts, list):
            raise APIError(
                message="Expected a list of posts from WordPress API.",
                status_code=response.status_code,
            )

        posts = [WPPost.from_api_response(p) for p in raw_posts if isinstance(p, dict)]

        return WPPostList(
            posts=posts,
            total=total,
            total_pages=total_pages,
            page=page,
            per_page=per_page,
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
        """Execute an HTTP request and return parsed JSON dict.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path relative to base_url.
            params: Optional query parameters.

        Returns:
            The parsed JSON response as a dictionary.
        """
        response = self._request_raw(method, path, params=params)
        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise APIError(
                message="Expected a JSON object from WordPress API.",
                status_code=response.status_code,
            )
        return data

    def _request_raw(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request and return the raw response.

        Translates all httpx exceptions to domain exceptions.

        Args:
            method: HTTP method.
            path: URL path relative to base_url.
            params: Optional query parameters.

        Returns:
            The raw :class:`httpx.Response`.

        Raises:
            AuthenticationError: On 401/403 responses.
            RateLimitError: On 429 responses.
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

        self._check_response_status(response)
        return response

    def _check_response_status(self, response: httpx.Response) -> None:
        """Validate the HTTP response status and raise on errors.

        Args:
            response: The httpx response object.

        Raises:
            AuthenticationError: On 401/403.
            RateLimitError: On 429.
            APIError: On other error status codes.
        """
        if response.status_code in (401, 403):
            logger.warning("Authentication failed (HTTP %d)", response.status_code)
            msg = self._extract_error_message(response)
            raise AuthenticationError(
                message=f"Authentication failed (HTTP {response.status_code}): {msg}",
            )

        if response.status_code == 429:
            logger.warning("Rate limited (HTTP 429)")
            raise RateLimitError()

        if response.status_code >= 400:
            logger.warning("API error (HTTP %d)", response.status_code)
            msg = self._extract_error_message(response)
            raise APIError(
                message=f"WordPress API error (HTTP {response.status_code}): {msg}",
                status_code=response.status_code,
            )

    @staticmethod
    def _parse_json(response: httpx.Response) -> object:
        """Parse the JSON body from a response.

        Returns:
            The parsed JSON (dict or list).

        Raises:
            APIError: If the body is not valid JSON.
        """
        try:
            return response.json()
        except Exception as exc:
            raise APIError(
                message="Failed to parse WordPress JSON response.",
                status_code=response.status_code,
            ) from exc

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract a human-readable error from a WordPress error response."""
        try:
            body = response.json()
            if isinstance(body, dict):
                return str(body.get("message", response.reason_phrase))
        except Exception:  # noqa: S110
            pass
        return response.reason_phrase or "Unknown error"

    def _detect_wp_version(self) -> str:
        """Attempt to detect the WordPress version.

        The version is not always exposed in the REST API for security
        reasons.  Falls back to ``"unknown"`` when it cannot be determined.
        """
        try:
            client = self._ensure_connected()
            response = client.request("GET", _WP_JSON_PATH)

            # The WP-Version header is sometimes available
            wp_header = response.headers.get("x-wp-version", "")
            if wp_header:
                return wp_header

            return "unknown"
        except Exception:
            return "unknown"
