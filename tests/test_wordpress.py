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
    TimeoutError,
    WordPressError,
)
from app.infrastructure.wordpress.models import WPHealthCheck, WPSiteInfo, WPUser


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def wp_client() -> WordPressClient:
    """Return a WordPressClient without connecting."""
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


# =============================================================================
# Client Tests
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

    def test_not_connected_by_default(self, wp_client: WordPressClient) -> None:
        """Client should not be connected after construction."""
        assert wp_client._client is None

    def test_request_before_connect_raises(self, wp_client: WordPressClient) -> None:
        """Calling methods before connect() should raise WordPressError."""
        with pytest.raises(WordPressError, match="not connected"):
            wp_client.get_site_info()


class TestWordPressClientConnect:
    """Tests for the connect / close lifecycle."""

    def test_connect_creates_httpx_client(self, wp_client: WordPressClient) -> None:
        """connect() should initialise the httpx client."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}

        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.request.return_value = mock_response

            wp_client.connect()

            assert wp_client._client is not None
            MockClient.assert_called_once()

    def test_close_clears_client(self, wp_client: WordPressClient) -> None:
        """close() should reset the internal client to None."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}

        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.request.return_value = mock_response

            wp_client.connect()
            wp_client.close()

            assert wp_client._client is None
            mock_instance.close.assert_called_once()

    def test_context_manager(self, wp_client: WordPressClient) -> None:
        """The client should work as a context manager."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Test"}

        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.request.return_value = mock_response

            with wp_client:
                assert wp_client._client is not None

            assert wp_client._client is None


class TestWordPressClientRequests:
    """Tests for HTTP request handling and error translation."""

    def _connect_client(
        self,
        wp_client: WordPressClient,
        mock_httpx: MagicMock,
    ) -> MagicMock:
        """Helper: connect the client with a mock httpx.Client."""
        connect_response = MagicMock(spec=httpx.Response)
        connect_response.status_code = 200
        connect_response.json.return_value = {"name": "Test"}

        mock_instance = mock_httpx.return_value
        mock_instance.request.return_value = connect_response

        wp_client.connect()
        return mock_instance

    def test_get_site_info(
        self,
        wp_client: WordPressClient,
        mock_site_info_json: dict[str, object],
    ) -> None:
        """get_site_info() should return a validated WPSiteInfo."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            site_response = MagicMock(spec=httpx.Response)
            site_response.status_code = 200
            site_response.json.return_value = mock_site_info_json
            mock_instance.request.return_value = site_response

            info = wp_client.get_site_info()
            assert info.name == "LokGeets"
            assert info.url == "https://example.com"

    def test_get_current_user(
        self,
        wp_client: WordPressClient,
        mock_user_json: dict[str, object],
    ) -> None:
        """get_current_user() should return a validated WPUser."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            user_response = MagicMock(spec=httpx.Response)
            user_response.status_code = 200
            user_response.json.return_value = mock_user_json
            mock_instance.request.return_value = user_response

            user = wp_client.get_current_user()
            assert user.name == "admin"
            assert user.id == 1

    def test_401_raises_authentication_error(self, wp_client: WordPressClient) -> None:
        """A 401 response should raise AuthenticationError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 401
            error_response.reason_phrase = "Unauthorized"
            error_response.json.return_value = {"message": "Invalid credentials"}
            mock_instance.request.return_value = error_response

            with pytest.raises(AuthenticationError):
                wp_client.get_site_info()

    def test_403_raises_authentication_error(self, wp_client: WordPressClient) -> None:
        """A 403 response should also raise AuthenticationError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 403
            error_response.reason_phrase = "Forbidden"
            error_response.json.return_value = {"message": "Forbidden"}
            mock_instance.request.return_value = error_response

            with pytest.raises(AuthenticationError):
                wp_client.get_site_info()

    def test_404_raises_api_error(self, wp_client: WordPressClient) -> None:
        """A 404 response should raise APIError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 404
            error_response.reason_phrase = "Not Found"
            error_response.json.return_value = {"message": "Route not found"}
            mock_instance.request.return_value = error_response

            with pytest.raises(APIError) as exc_info:
                wp_client.get_site_info()
            assert exc_info.value.status_code == 404

    def test_500_raises_api_error(self, wp_client: WordPressClient) -> None:
        """A 500 response should raise APIError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            error_response = MagicMock(spec=httpx.Response)
            error_response.status_code = 500
            error_response.reason_phrase = "Internal Server Error"
            error_response.json.return_value = {"message": "Server error"}
            mock_instance.request.return_value = error_response

            with pytest.raises(APIError) as exc_info:
                wp_client.get_site_info()
            assert exc_info.value.status_code == 500

    def test_timeout_raises_timeout_error(self, wp_client: WordPressClient) -> None:
        """An httpx timeout should raise our TimeoutError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            mock_instance.request.side_effect = httpx.TimeoutException("timed out")

            with pytest.raises(TimeoutError):
                wp_client.get_site_info()

    def test_connect_error_raises_connection_error(self, wp_client: WordPressClient) -> None:
        """An httpx ConnectError should raise our ConnectionError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            mock_instance.request.side_effect = httpx.ConnectError("DNS failed")

            with pytest.raises(ConnectionError):
                wp_client.get_site_info()

    def test_generic_http_error_raises_connection_error(
        self, wp_client: WordPressClient
    ) -> None:
        """Any other httpx.HTTPError should raise our ConnectionError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            mock_instance.request.side_effect = httpx.HTTPError("network down")

            with pytest.raises(ConnectionError):
                wp_client.get_site_info()

    def test_invalid_json_raises_api_error(self, wp_client: WordPressClient) -> None:
        """A response with unparseable JSON should raise APIError."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = self._connect_client(wp_client, MockClient)

            bad_response = MagicMock(spec=httpx.Response)
            bad_response.status_code = 200
            bad_response.json.side_effect = ValueError("Invalid JSON")
            mock_instance.request.return_value = bad_response

            with pytest.raises(APIError, match="parse"):
                wp_client.get_site_info()


class TestWordPressClientHealthCheck:
    """Tests for the health_check() aggregate method."""

    def test_health_check_returns_aggregate(
        self,
        wp_client: WordPressClient,
        mock_site_info_json: dict[str, object],
        mock_user_json: dict[str, object],
    ) -> None:
        """health_check() should return a WPHealthCheck with all fields."""
        with patch("app.infrastructure.wordpress.client.httpx.Client") as MockClient:
            mock_instance = MockClient.return_value

            # Connect probe response
            connect_response = MagicMock(spec=httpx.Response)
            connect_response.status_code = 200
            connect_response.json.return_value = mock_site_info_json

            # Site info response
            site_response = MagicMock(spec=httpx.Response)
            site_response.status_code = 200
            site_response.json.return_value = mock_site_info_json

            # User response
            user_response = MagicMock(spec=httpx.Response)
            user_response.status_code = 200
            user_response.json.return_value = mock_user_json

            # Version detection response
            version_response = MagicMock(spec=httpx.Response)
            version_response.status_code = 200
            version_response.json.return_value = mock_site_info_json
            version_response.headers = {"x-wp-version": "6.5.2"}

            mock_instance.request.side_effect = [
                connect_response,  # connect()
                site_response,     # get_site_info()
                user_response,     # get_current_user()
                version_response,  # _detect_wp_version()
            ]

            wp_client.connect()
            health = wp_client.health_check()

            assert isinstance(health, WPHealthCheck)
            assert health.site_info.name == "LokGeets"
            assert health.current_user.name == "admin"
            assert health.wp_version == "6.5.2"
            assert health.rest_api_healthy is True
