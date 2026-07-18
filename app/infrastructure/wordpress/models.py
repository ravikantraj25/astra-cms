"""Pydantic models representing WordPress REST API responses.

These models validate and structure the JSON payloads returned by
WordPress, providing type-safe access to site metadata, user information,
and post content.
"""

from __future__ import annotations

import re

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


# ── HTML helpers ─────────────────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    return _HTML_TAG_RE.sub("", html).strip()


def _word_count(html: str) -> int:
    """Count words in an HTML string after stripping tags."""
    return len(_strip_html(html).split())


def _extract_rendered(data: dict[str, object], key: str) -> str:
    """Extract a ``{rendered: ...}`` field from a WordPress API dict."""
    obj = data.get(key, {})
    if isinstance(obj, dict):
        return str(obj.get("rendered", ""))
    return str(obj)


# ── Post Models ──────────────────────────────────────────────────────────────


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
    content_html: str = Field(default="", description="Full post content (rendered HTML).")
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
        title = _extract_rendered(data, "title")
        excerpt = _extract_rendered(data, "excerpt")
        content_html = _extract_rendered(data, "content")

        raw_id = data.get("id", 0)
        post_id: int = raw_id if isinstance(raw_id, int) else int(str(raw_id))

        raw_author = data.get("author", 0)
        author_id: int = raw_author if isinstance(raw_author, int) else int(str(raw_author))

        return cls(
            id=post_id,
            title=title,
            slug=str(data.get("slug", "")),
            status=str(data.get("status", "publish")),
            link=str(data.get("link", "")),
            date=str(data.get("date", "")),
            modified=str(data.get("modified", "")),
            excerpt=excerpt,
            content_html=content_html,
            author=author_id,
        )


class WPPostDetail(BaseModel):
    """Enriched single-post view with taxonomy and word count.

    Built from a :class:`WPPost` plus supplementary API data
    (categories, tags, author name).
    """

    post: WPPost = Field(description="The core post data.")
    author_name: str = Field(default="Unknown", description="Author display name.")
    categories: list[str] = Field(default_factory=list, description="Category names.")
    tags: list[str] = Field(default_factory=list, description="Tag names.")
    word_count: int = Field(default=0, description="Approximate word count.")


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
