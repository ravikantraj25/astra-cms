"""Comprehensive tests for the WordPress client, models, and exceptions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

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
    _strip_html,
    _word_count,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def mock_httpx_client() -> MagicMock:
    """Return a mock httpx.Client for dependency injection."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture()
def wp_client(mock_httpx_client: MagicMock) -> WordPressClient:
    """Return a WordPressClient with an injected mock httpx.Client."""
    return WordPressClient(
        base_url="https://example.com",
        http_client=mock_httpx_client,
    )


@pytest.fixture()
def wp_client_no_inject() -> WordPressClient:
    """Return a WordPressClient without DI (for legacy-style tests)."""
    return WordPressClient(
        base_url="https://example.com",
        username="admin",
        app_password="test-app-password",
    )


@pytest.fixture()
def mock_site_info_json() -> dict[str, object]:
    """Return a realistic WordPress REST API root response."""
    return {
        "name": "LokGeets",
        "description": "A test WordPress site",
        "url": "https://example.com",
        "home": "https://example.com",
        "gmt_offset": 5.5,
        "timezone_string": "Asia/Kolkata",
        "namespaces": ["wp/v2", "oembed/1.0"],
    }


@pytest.fixture()
def mock_user_json() -> dict[str, object]:
    """Return a realistic WordPress /users/me response."""
    return {
        "id": 1,
        "name": "admin",
        "slug": "admin",
        "link": "https://example.com/author/admin/",
        "roles": ["administrator"],
    }


@pytest.fixture()
def mock_posts_json() -> list[dict[str, object]]:
    """Return a realistic WordPress /wp/v2/posts response."""
    return [
        {
            "id": 120,
            "title": {"rendered": "Diwali NYC 2026"},
            "slug": "diwali-nyc-2026",
            "status": "publish",
            "link": "https://example.com/diwali-nyc-2026/",
            "date": "2026-07-15T10:00:00",
            "modified": "2026-07-15T12:00:00",
            "excerpt": {"rendered": "Celebrating Diwali in New York City."},
            "author": 1,
        },
        {
            "id": 121,
            "title": {"rendered": "Chhath USA"},
            "slug": "chhath-usa",
            "status": "publish",
            "link": "https://example.com/chhath-usa/",
            "date": "2026-07-14T09:00:00",
            "modified": "2026-07-14T11:00:00",
            "excerpt": {"rendered": "Chhath celebrations across America."},
            "author": 1,
        },
        {
            "id": 122,
            "title": {"rendered": "Holi Boston"},
            "slug": "holi-boston",
            "status": "draft",
            "link": "https://example.com/holi-boston/",
            "date": "2026-07-13T08:00:00",
            "modified": "2026-07-13T10:00:00",
            "excerpt": {"rendered": "Holi in Boston."},
            "author": 2,
        },
    ]


# =============================================================================
# Exception Tests
# =============================================================================


class TestExceptions:
    """Tests for WordPress exception hierarchy."""

    def test_wordpress_error_is_base(self) -> None:
        """All WordPress exceptions should inherit from WordPressError."""
        assert issubclass(AuthenticationError, WordPressError)
        assert issubclass(ConnectionError, WordPressError)
        assert issubclass(TimeoutError, WordPressError)
        assert issubclass(APIError, WordPressError)
        assert issubclass(RateLimitError, WordPressError)

    def test_authentication_error_defaults(self) -> None:
        """AuthenticationError should default to status 401."""
        exc = AuthenticationError()
        assert exc.status_code == 401
        assert "Authentication" in exc.message

    def test_connection_error_defaults(self) -> None:
        """ConnectionError should have no status code."""
        exc = ConnectionError()
        assert exc.status_code is None
        assert "connect" in exc.message.lower()

    def test_timeout_error_defaults(self) -> None:
        """TimeoutError should have no status code."""
        exc = TimeoutError()
        assert exc.status_code is None
        assert "timed out" in exc.message.lower()

    def test_rate_limit_error_defaults(self) -> None:
        """RateLimitError should default to status 429."""
        exc = RateLimitError()
        assert exc.status_code == 429
        assert "rate" in exc.message.lower()

    def test_api_error_with_status(self) -> None:
        """APIError should accept a custom status code."""
        exc = APIError(message="Not found", status_code=404)
        assert exc.status_code == 404
        assert exc.message == "Not found"

    def test_wordpress_error_custom_message(self) -> None:
        """WordPressError should store the custom message."""
        exc = WordPressError("Something broke", status_code=500)
        assert str(exc) == "Something broke"
        assert exc.status_code == 500


# =============================================================================
# Model Tests
# =============================================================================


class TestModels:
    """Tests for WordPress Pydantic models."""

    def test_site_info_from_dict(self, mock_site_info_json: dict[str, object]) -> None:
        """WPSiteInfo should parse a valid REST API root response."""
        info = WPSiteInfo.model_validate(mock_site_info_json)
        assert info.name == "LokGeets"
        assert info.url == "https://example.com"
        assert "wp/v2" in info.namespaces

    def test_site_info_defaults(self) -> None:
        """WPSiteInfo should use defaults for missing optional fields."""
        info = WPSiteInfo(name="Test", url="https://test.com")
        assert info.description == ""
        assert info.namespaces == []
        assert info.gmt_offset == 0.0

    def test_user_from_dict(self, mock_user_json: dict[str, object]) -> None:
        """WPUser should parse a valid /users/me response."""
        user = WPUser.model_validate(mock_user_json)
        assert user.id == 1
        assert user.name == "admin"
        assert "administrator" in user.roles

    def test_user_defaults(self) -> None:
        """WPUser should use defaults for missing optional fields."""
        user = WPUser(id=1, name="test")
        assert user.slug == ""
        assert user.roles == []

    def test_health_check_model(
        self,
        mock_site_info_json: dict[str, object],
        mock_user_json: dict[str, object],
    ) -> None:
        """WPHealthCheck should aggregate site info and user."""
        health = WPHealthCheck(
            site_info=WPSiteInfo.model_validate(mock_site_info_json),
            current_user=WPUser.model_validate(mock_user_json),
            wp_version="6.5",
            rest_api_healthy=True,
        )
        assert health.site_info.name == "LokGeets"
        assert health.current_user.name == "admin"
        assert health.wp_version == "6.5"
        assert health.rest_api_healthy is True


class TestPostModel:
    """Tests for the WPPost model."""

    def test_post_from_api_response(self) -> None:
        """WPPost.from_api_response should flatten rendered fields."""
        raw = {
            "id": 120,
            "title": {"rendered": "Diwali NYC 2026"},
            "slug": "diwali-nyc-2026",
            "status": "publish",
            "link": "https://example.com/diwali-nyc-2026/",
            "date": "2026-07-15T10:00:00",
            "modified": "2026-07-15T12:00:00",
            "excerpt": {"rendered": "Celebrating Diwali."},
            "author": 1,
        }
        post = WPPost.from_api_response(raw)
        assert post.id == 120
        assert post.title == "Diwali NYC 2026"
        assert post.status == "publish"
        assert post.excerpt == "Celebrating Diwali."

    def test_post_from_api_response_missing_fields(self) -> None:
        """WPPost should handle missing optional fields gracefully."""
        raw: dict[str, object] = {"id": 1, "title": {"rendered": "Test"}}
        post = WPPost.from_api_response(raw)
        assert post.id == 1
        assert post.title == "Test"
        assert post.status == "publish"
        assert post.excerpt == ""

    def test_post_from_api_response_plain_title(self) -> None:
        """WPPost should handle non-dict title gracefully."""
        raw: dict[str, object] = {"id": 1, "title": "Plain Title"}
        post = WPPost.from_api_response(raw)
        assert post.title == "Plain Title"

    def test_post_list_model(self) -> None:
        """WPPostList should hold posts with pagination metadata."""
        post = WPPost(id=1, title="Test")
        post_list = WPPostList(posts=[post], total=50, total_pages=5, page=1, per_page=10)
        assert len(post_list.posts) == 1
        assert post_list.total == 50
        assert post_list.total_pages == 5


# =============================================================================
# Client Tests — DI-based (injected httpx.Client)
# =============================================================================


class TestWordPressClientInit:
    """Tests for WordPressClient initialisation."""

    def test_base_url_trailing_slash_stripped(self) -> None:
        """Trailing slashes should be removed from the base URL."""
        client = WordPressClient(
            base_url="https://example.com/",
            username="admin",
            app_password="pass",
        )
        assert client._base_url == "https://example.com"

    def test_not_connected_by_default(self) -> None:
        """Client without DI should not be connected after construction."""
        client = WordPressClient(
            base_url="https://example.com",
            username="admin",
            app_password="pass",
        )
        assert client._client is None

    def test_injected_client_is_set(self, wp_client: WordPressClient) -> None:
        """Client with DI should have _client set immediately."""
        assert wp_client._client is not None

    def test_request_before_connect_raises(self) -> None:
        """Calling methods before connect() without DI should raise."""
        client = WordPressClient(
            base_url="https://example.com",
            username="admin",
            app_password="pass",
        )
        with pytest.raises(WordPressError, match="not connected"):
            client.get_site_info()


class TestWordPressClientConnect:
    """Tests for the connect / close lifecycle."""

    def test_connect_with_injected_client(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """connect() with injected client should probe without creating new client."""
        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.json.return_value = {"name": "Test"}
        mock_httpx_client.request.return_value = ok_response

        wp_client.connect()
        # The injected client should be used, not replaced
        assert wp_client._client is mock_httpx_client

    def test_connect_creates_httpx_client_when_no_injection(
        self,
        wp_client_no_inject: WordPressClient,
    ) -> None:
        """connect() without DI should create its own httpx.Client."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}

        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.request.return_value = mock_response

            wp_client_no_inject.connect()

            assert wp_client_no_inject._client is not None
            MockClient.assert_called_once()

    def test_close_clears_client(self, wp_client_no_inject: WordPressClient) -> None:
        """close() should reset the internal client to None."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}

        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.request.return_value = mock_response

            wp_client_no_inject.connect()
            wp_client_no_inject.close()

            assert wp_client_no_inject._client is None
            mock_instance.close.assert_called_once()

    def test_close_does_not_close_injected_client(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """close() should NOT close an injected client (caller owns it)."""
        wp_client.close()
        mock_httpx_client.close.assert_not_called()
        assert wp_client._client is None

    def test_context_manager(self, wp_client_no_inject: WordPressClient) -> None:
        """The client should work as a context manager."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}

        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.request.return_value = mock_response

            with wp_client_no_inject:
                assert wp_client_no_inject._client is not None

            assert wp_client_no_inject._client is None


class TestWordPressClientRequests:
    """Tests for HTTP request handling and error translation."""

    def test_get_site_info(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
        mock_site_info_json: dict[str, object],
    ) -> None:
        """get_site_info() should return a validated WPSiteInfo."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = mock_site_info_json
        mock_httpx_client.request.return_value = response

        info = wp_client.get_site_info()
        assert info.name == "LokGeets"
        assert info.url == "https://example.com"

    def test_get_current_user(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
        mock_user_json: dict[str, object],
    ) -> None:
        """get_current_user() should return a validated WPUser."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = mock_user_json
        mock_httpx_client.request.return_value = response

        user = wp_client.get_current_user()
        assert user.name == "admin"
        assert user.id == 1

    def test_401_raises_authentication_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """A 401 response should raise AuthenticationError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.reason_phrase = "Unauthorized"
        response.json.return_value = {"message": "Invalid credentials"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(AuthenticationError):
            wp_client.get_site_info()

    def test_403_raises_authentication_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """A 403 response should also raise AuthenticationError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.reason_phrase = "Forbidden"
        response.json.return_value = {"message": "Forbidden"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(AuthenticationError):
            wp_client.get_site_info()

    def test_429_raises_rate_limit_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """A 429 response should raise RateLimitError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.reason_phrase = "Too Many Requests"
        response.json.return_value = {"message": "Rate limited"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(RateLimitError):
            wp_client.get_site_info()

    def test_404_raises_api_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """A 404 response should raise APIError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        response.reason_phrase = "Not Found"
        response.json.return_value = {"message": "Route not found"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(APIError) as exc_info:
            wp_client.get_site_info()
        assert exc_info.value.status_code == 404

    def test_500_raises_api_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """A 500 response should raise APIError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500
        response.reason_phrase = "Internal Server Error"
        response.json.return_value = {"message": "Server error"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(APIError) as exc_info:
            wp_client.get_site_info()
        assert exc_info.value.status_code == 500

    def test_timeout_raises_timeout_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """An httpx timeout should raise our TimeoutError."""
        mock_httpx_client.request.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(TimeoutError):
            wp_client.get_site_info()

    def test_connect_error_raises_connection_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """An httpx ConnectError should raise our ConnectionError."""
        mock_httpx_client.request.side_effect = httpx.ConnectError("DNS failed")

        with pytest.raises(ConnectionError):
            wp_client.get_site_info()

    def test_generic_http_error_raises_connection_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """Any other httpx.HTTPError should raise our ConnectionError."""
        mock_httpx_client.request.side_effect = httpx.HTTPError("network down")

        with pytest.raises(ConnectionError):
            wp_client.get_site_info()

    def test_invalid_json_raises_api_error(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """A response with unparseable JSON should raise APIError."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("Invalid JSON")
        mock_httpx_client.request.return_value = response

        with pytest.raises(APIError, match="parse"):
            wp_client.get_site_info()


# =============================================================================
# Health Check Tests
# =============================================================================


class TestWordPressClientHealthCheck:
    """Tests for the health_check() aggregate method."""

    def test_health_check_returns_aggregate(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
        mock_site_info_json: dict[str, object],
        mock_user_json: dict[str, object],
    ) -> None:
        """health_check() should return a WPHealthCheck with all fields."""
        site_response = MagicMock(spec=httpx.Response)
        site_response.status_code = 200
        site_response.json.return_value = mock_site_info_json

        user_response = MagicMock(spec=httpx.Response)
        user_response.status_code = 200
        user_response.json.return_value = mock_user_json

        version_response = MagicMock(spec=httpx.Response)
        version_response.status_code = 200
        version_response.json.return_value = mock_site_info_json
        version_response.headers = {"x-wp-version": "6.5.2"}

        mock_httpx_client.request.side_effect = [
            site_response,  # get_site_info()
            user_response,  # get_current_user()
            version_response,  # _detect_wp_version()
        ]

        health = wp_client.health_check()

        assert isinstance(health, WPHealthCheck)
        assert health.site_info.name == "LokGeets"
        assert health.current_user.name == "admin"
        assert health.wp_version == "6.5.2"
        assert health.rest_api_healthy is True


# =============================================================================
# Get Posts Tests
# =============================================================================


class TestWordPressClientGetPosts:
    """Tests for the get_posts() method."""

    def test_get_posts_success(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
        mock_posts_json: list[dict[str, object]],
    ) -> None:
        """get_posts() should return a WPPostList with parsed posts."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = mock_posts_json
        response.headers = {"X-WP-Total": "3", "X-WP-TotalPages": "1"}
        mock_httpx_client.request.return_value = response

        result = wp_client.get_posts()

        assert isinstance(result, WPPostList)
        assert len(result.posts) == 3
        assert result.posts[0].title == "Diwali NYC 2026"
        assert result.posts[0].id == 120
        assert result.posts[2].status == "draft"
        assert result.total == 3
        assert result.total_pages == 1

    def test_get_posts_empty(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_posts() should handle an empty result list."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = []
        response.headers = {"X-WP-Total": "0", "X-WP-TotalPages": "0"}
        mock_httpx_client.request.return_value = response

        result = wp_client.get_posts()

        assert len(result.posts) == 0
        assert result.total == 0

    def test_get_posts_with_search(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
        mock_posts_json: list[dict[str, object]],
    ) -> None:
        """get_posts(search=...) should pass the search param to WordPress."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = [mock_posts_json[0]]
        response.headers = {"X-WP-Total": "1", "X-WP-TotalPages": "1"}
        mock_httpx_client.request.return_value = response

        result = wp_client.get_posts(search="Diwali")

        assert len(result.posts) == 1
        assert result.posts[0].title == "Diwali NYC 2026"

        # Verify search was passed in the request params
        call_args = mock_httpx_client.request.call_args
        assert call_args.kwargs.get("params", {}).get("search") == "Diwali"

    def test_get_posts_pagination(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
        mock_posts_json: list[dict[str, object]],
    ) -> None:
        """get_posts(page=2) should pass page param to WordPress."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = mock_posts_json
        response.headers = {"X-WP-Total": "30", "X-WP-TotalPages": "3"}
        mock_httpx_client.request.return_value = response

        result = wp_client.get_posts(page=2, per_page=10)

        assert result.page == 2
        assert result.per_page == 10
        assert result.total_pages == 3

        call_args = mock_httpx_client.request.call_args
        assert call_args.kwargs.get("params", {}).get("page") == "2"

    def test_get_posts_auth_failure(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_posts() should raise AuthenticationError on 401."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.reason_phrase = "Unauthorized"
        response.json.return_value = {"message": "Invalid credentials"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(AuthenticationError):
            wp_client.get_posts()

    def test_get_posts_timeout(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_posts() should raise TimeoutError on timeout."""
        mock_httpx_client.request.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(TimeoutError):
            wp_client.get_posts()

    def test_get_posts_malformed_response(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_posts() should raise APIError for non-list JSON response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {"error": "unexpected"}
        response.headers = {"X-WP-Total": "0", "X-WP-TotalPages": "0"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(APIError, match="list"):
            wp_client.get_posts()

    def test_get_posts_per_page_clamped(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_posts() should clamp per_page between 1 and 100."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = []
        response.headers = {"X-WP-Total": "0", "X-WP-TotalPages": "0"}
        mock_httpx_client.request.return_value = response

        wp_client.get_posts(per_page=200)

        call_args = mock_httpx_client.request.call_args
        assert call_args.kwargs.get("params", {}).get("per_page") == "100"


# =============================================================================
# HTML Helper Tests
# =============================================================================


class TestModelHelpers:
    """Tests for _strip_html and _word_count utility functions."""

    def test_strip_html_removes_tags(self) -> None:
        """_strip_html should remove all HTML tags."""
        assert _strip_html("<p>Hello <strong>World</strong></p>") == "Hello World"

    def test_strip_html_empty(self) -> None:
        """_strip_html should handle empty strings."""
        assert _strip_html("") == ""

    def test_word_count_basic(self) -> None:
        """_word_count should count words after stripping HTML."""
        assert _word_count("<p>One two three four five</p>") == 5

    def test_word_count_empty(self) -> None:
        """_word_count should return 0 for empty content."""
        assert _word_count("") == 0


# =============================================================================
# WPPostDetail Model Tests
# =============================================================================


class TestPostDetailModel:
    """Tests for the WPPostDetail model."""

    def test_post_detail_model(self) -> None:
        """WPPostDetail should hold a post with enriched metadata."""
        post = WPPost(id=123, title="Test", content_html="<p>Hello world</p>")
        detail = WPPostDetail(
            post=post,
            author_name="Admin",
            categories=["Festivals"],
            tags=["Diwali", "USA"],
            word_count=2,
        )
        assert detail.post.id == 123
        assert detail.author_name == "Admin"
        assert detail.categories == ["Festivals"]
        assert detail.tags == ["Diwali", "USA"]
        assert detail.word_count == 2


# =============================================================================
# Get Single Post Tests
# =============================================================================


class TestWordPressClientGetPost:
    """Tests for the get_post() method."""

    def test_get_post_success(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_post() should return a WPPostDetail with enriched metadata."""
        post_json = {
            "id": 123,
            "title": {"rendered": "Diwali Celebration NYC"},
            "slug": "diwali-celebration-nyc",
            "status": "publish",
            "link": "https://example.com/diwali-celebration-nyc/",
            "date": "2026-09-20T10:00:00",
            "modified": "2026-09-20T12:00:00",
            "excerpt": {"rendered": "Celebrating Diwali in NYC."},
            "content": {"rendered": "<p>Diwali is the festival of lights.</p>"},
            "author": 1,
            "categories": [5],
            "tags": [10, 11],
        }
        author_json = {"id": 1, "name": "Admin", "slug": "admin"}
        cat_json = {"id": 5, "name": "Festivals"}
        tag1_json = {"id": 10, "name": "Diwali"}
        tag2_json = {"id": 11, "name": "USA"}

        post_resp = MagicMock(spec=httpx.Response)
        post_resp.status_code = 200
        post_resp.json.return_value = post_json

        author_resp = MagicMock(spec=httpx.Response)
        author_resp.status_code = 200
        author_resp.json.return_value = author_json

        cat_resp = MagicMock(spec=httpx.Response)
        cat_resp.status_code = 200
        cat_resp.json.return_value = cat_json

        tag1_resp = MagicMock(spec=httpx.Response)
        tag1_resp.status_code = 200
        tag1_resp.json.return_value = tag1_json

        tag2_resp = MagicMock(spec=httpx.Response)
        tag2_resp.status_code = 200
        tag2_resp.json.return_value = tag2_json

        mock_httpx_client.request.side_effect = [
            post_resp,  # GET /posts/123
            author_resp,  # GET /users/1
            cat_resp,  # GET /categories/5
            tag1_resp,  # GET /tags/10
            tag2_resp,  # GET /tags/11
        ]

        detail = wp_client.get_post(123)

        assert detail.post.id == 123
        assert detail.post.title == "Diwali Celebration NYC"
        assert detail.author_name == "Admin"
        assert detail.categories == ["Festivals"]
        assert detail.tags == ["Diwali", "USA"]
        assert detail.word_count == 6
        assert detail.post.content_html == "<p>Diwali is the festival of lights.</p>"

    def test_get_post_404(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_post() should raise APIError for a 404 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        response.reason_phrase = "Not Found"
        response.json.return_value = {"message": "Post not found"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(APIError) as exc_info:
            wp_client.get_post(99999)
        assert exc_info.value.status_code == 404

    def test_get_post_auth_failure(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_post() should raise AuthenticationError on 401."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.reason_phrase = "Unauthorized"
        response.json.return_value = {"message": "Invalid credentials"}
        mock_httpx_client.request.return_value = response

        with pytest.raises(AuthenticationError):
            wp_client.get_post(123)

    def test_get_post_timeout(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_post() should raise TimeoutError on timeout."""
        mock_httpx_client.request.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(TimeoutError):
            wp_client.get_post(123)

    def test_get_post_author_resolution_failure(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_post() should use 'Unknown' when author lookup fails."""
        post_json = {
            "id": 123,
            "title": {"rendered": "Test Post"},
            "content": {"rendered": "<p>Content</p>"},
            "author": 999,
            "categories": [],
            "tags": [],
        }
        post_resp = MagicMock(spec=httpx.Response)
        post_resp.status_code = 200
        post_resp.json.return_value = post_json

        # Author lookup returns 404
        author_resp = MagicMock(spec=httpx.Response)
        author_resp.status_code = 404
        author_resp.reason_phrase = "Not Found"
        author_resp.json.return_value = {"message": "User not found"}

        mock_httpx_client.request.side_effect = [post_resp, author_resp]

        detail = wp_client.get_post(123)

        assert detail.author_name == "Unknown"
        assert detail.post.id == 123

    def test_get_post_no_taxonomy(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """get_post() should handle posts with no categories or tags."""
        post_json = {
            "id": 123,
            "title": {"rendered": "Simple Post"},
            "content": {"rendered": "<p>Just text</p>"},
            "author": 1,
        }
        post_resp = MagicMock(spec=httpx.Response)
        post_resp.status_code = 200
        post_resp.json.return_value = post_json

        author_resp = MagicMock(spec=httpx.Response)
        author_resp.status_code = 200
        author_resp.json.return_value = {"id": 1, "name": "Admin"}

        mock_httpx_client.request.side_effect = [post_resp, author_resp]

        detail = wp_client.get_post(123)

        assert detail.categories == []
        assert detail.tags == []
        assert detail.word_count == 2


# =============================================================================
# update_post Tests
# =============================================================================


class TestUpdatePost:
    """Tests for WordPressClient.update_post."""

    def test_update_post_success(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """update_post() should send a POST with status=draft."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {
            "id": 123,
            "title": {"rendered": "Updated"},
            "content": {"rendered": "<p>New</p>"},
            "status": "draft",
            "link": "https://example.com/?p=123&preview=true",
        }
        mock_httpx_client.request.return_value = response

        result = wp_client.update_post(
            post_id=123,
            title="Updated",
            content="<p>New</p>",
            status="draft",
        )

        assert result.id == 123
        assert result.status == "draft"
        assert result.link == "https://example.com/?p=123&preview=true"

        # Verify the request was built with json body
        call_args = mock_httpx_client.request.call_args_list[0]
        assert call_args.kwargs["json"]["status"] == "draft"
        assert call_args.kwargs["json"]["title"] == "Updated"
        assert call_args.kwargs["json"]["content"] == "<p>New</p>"

    def test_update_post_blocks_publish(
        self,
        wp_client: WordPressClient,
    ) -> None:
        """update_post() should refuse status='publish'."""
        with pytest.raises(ValueError, match=r"Only \"draft\" is allowed"):
            wp_client.update_post(post_id=123, status="publish")

    def test_update_post_404(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """update_post() should raise APIError for a 404 post."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        response.json.return_value = {"message": "Not found"}
        response.reason_phrase = "Not Found"
        mock_httpx_client.request.return_value = response

        with pytest.raises(APIError):
            wp_client.update_post(post_id=99999, content="<p>Test</p>")

    def test_update_post_auth_failure(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """update_post() should raise AuthenticationError on 401."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.json.return_value = {"message": "Unauthorized"}
        response.reason_phrase = "Unauthorized"
        mock_httpx_client.request.return_value = response

        with pytest.raises(AuthenticationError):
            wp_client.update_post(post_id=123, content="<p>Test</p>")

    def test_update_post_timeout(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """update_post() should raise TimeoutError on timeout."""
        mock_httpx_client.request.side_effect = httpx.ReadTimeout("read timed out")

        with pytest.raises(TimeoutError):
            wp_client.update_post(post_id=123, content="<p>Test</p>")

    def test_update_post_content_only(
        self,
        wp_client: WordPressClient,
        mock_httpx_client: MagicMock,
    ) -> None:
        """update_post() should only include content when title is None."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {
            "id": 123,
            "title": {"rendered": "Original Title"},
            "content": {"rendered": "<p>New content</p>"},
            "status": "draft",
        }
        mock_httpx_client.request.return_value = response

        wp_client.update_post(post_id=123, content="<p>New content</p>")

        call_args = mock_httpx_client.request.call_args_list[0]
        json_body = call_args.kwargs["json"]
        assert "title" not in json_body
        assert json_body["content"] == "<p>New content</p>"
