"""Pydantic models representing WordPress REST API responses.

These models validate and structure the JSON payloads returned by
WordPress, providing type-safe access to site metadata, user information,
and post content.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WPSiteInfo(BaseModel):
    """WordPress site metadata from ``GET /``."""

    name: str = Field(description="The site title.")
    description: str = Field(default="", description="The site tagline.")
    url: str = Field(description="The site URL.")
    home: str = Field(default="", description="The home URL.")
    gmt_offset: float = Field(default=0.0, description="GMT offset in hours.")
    timezone_string: str = Field(default="", description="Timezone identifier.")

    # Namespaces indicate which REST API extensions are available
    namespaces: list[str] = Field(default_factory=list, description="Available REST namespaces.")


class WPUser(BaseModel):
    """WordPress user from ``GET /wp/v2/users/me``."""

    id: int = Field(description="User ID.")
    name: str = Field(description="Display name.")
    slug: str = Field(default="", description="URL-friendly username.")
    link: str = Field(default="", description="Profile URL.")
    roles: list[str] = Field(default_factory=list, description="Assigned roles.")


class WPPost(BaseModel):
    """WordPress post from ``GET /wp/v2/posts``.

    Maps the most commonly used fields from the WordPress REST API
    post response.  The ``title`` and ``content`` are extracted from
    WordPress's ``{rendered: ...}`` wrapper objects.
    """

    id: int = Field(description="Post ID.")
    title: str = Field(default="", description="Post title (rendered).")
    slug: str = Field(default="", description="URL-friendly slug.")
    status: str = Field(default="publish", description="Post status.")
    link: str = Field(default="", description="Permalink URL.")
    date: str = Field(default="", description="Publication date (ISO 8601).")
    modified: str = Field(default="", description="Last modified date (ISO 8601).")
    excerpt: str = Field(default="", description="Post excerpt (rendered).")
    author: int = Field(default=0, description="Author user ID.")

    @classmethod
    def from_api_response(cls, data: dict[str, object]) -> WPPost:
        """Create a WPPost from a raw WordPress REST API post object.

        WordPress wraps title, content, and excerpt in ``{rendered: ...}``
        objects.  This factory method flattens that structure.

        Args:
            data: A single post dict from the WordPress API.

        Returns:
            A validated :class:`WPPost`.
        """
        title_obj = data.get("title", {})
        title = title_obj.get("rendered", "") if isinstance(title_obj, dict) else str(title_obj)

        excerpt_obj = data.get("excerpt", {})
        excerpt = (
            excerpt_obj.get("rendered", "") if isinstance(excerpt_obj, dict) else str(excerpt_obj)
        )

        return cls(
            id=int(data.get("id", 0)),  # type: ignore[arg-type]
            title=title,
            slug=str(data.get("slug", "")),
            status=str(data.get("status", "publish")),
            link=str(data.get("link", "")),
            date=str(data.get("date", "")),
            modified=str(data.get("modified", "")),
            excerpt=excerpt,
            author=int(data.get("author", 0)),  # type: ignore[arg-type]
        )


class WPPostList(BaseModel):
    """Paginated list of WordPress posts."""

    posts: list[WPPost] = Field(default_factory=list, description="List of posts.")
    total: int = Field(default=0, description="Total posts matching the query.")
    total_pages: int = Field(default=0, description="Total pages available.")
    page: int = Field(default=1, description="Current page number.")
    per_page: int = Field(default=10, description="Posts per page.")


class WPHealthCheck(BaseModel):
    """Aggregated health-check result for the WordPress connection."""

    site_info: WPSiteInfo = Field(description="Site metadata.")
    current_user: WPUser = Field(description="Authenticated user details.")
    wp_version: str = Field(default="unknown", description="WordPress version string.")
    rest_api_healthy: bool = Field(default=False, description="Whether the REST API responded.")
