"""Pydantic models representing WordPress REST API responses.

These models validate and structure the JSON payloads returned by
WordPress, providing type-safe access to site metadata and user information.
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


class WPHealthCheck(BaseModel):
    """Aggregated health-check result for the WordPress connection."""

    site_info: WPSiteInfo = Field(description="Site metadata.")
    current_user: WPUser = Field(description="Authenticated user details.")
    wp_version: str = Field(default="unknown", description="WordPress version string.")
    rest_api_healthy: bool = Field(default=False, description="Whether the REST API responded.")
