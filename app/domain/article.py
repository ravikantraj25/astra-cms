"""Domain models for parsed articles."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Image(BaseModel):
    """An image extracted from an article."""

    src: str = Field(description="The source URL of the image.")
    alt: str = Field(default="", description="The alternative text.")
    title: str = Field(default="", description="The title attribute.")


class Link(BaseModel):
    """A hyperlink extracted from an article."""

    href: str = Field(description="The URL of the link.")
    text: str = Field(default="", description="The clickable text.")
    title: str = Field(default="", description="The title attribute.")


class Section(BaseModel):
    """A detected section within the article."""

    name: str = Field(description="Name of the section (e.g., Introduction, Conclusion).")
    type: str = Field(description="Type of the section (e.g., introduction, heading, image).")
    astra_id: str = Field(description="Unique data-astra-id assigned to this section's root tag.")
    content: str = Field(description="The textual content or raw HTML of this section.")


class Article(BaseModel):
    """A structured representation of a parsed HTML article."""

    raw_html: str = Field(default="", description="The original raw HTML string.")
    title: str = Field(default="", description="The title of the article (from title tag or h1).")
    meta_description: str = Field(default="", description="The meta description if present.")
    headings: list[str] = Field(default_factory=list, description="All heading texts (h1-h6).")
    paragraphs: list[str] = Field(default_factory=list, description="All paragraph texts.")
    images: list[Image] = Field(default_factory=list, description="Extracted images.")
    links: list[Link] = Field(default_factory=list, description="Extracted links.")
    tables: list[str] = Field(default_factory=list, description="Raw HTML of tables.")
    lists: list[str] = Field(default_factory=list, description="Raw HTML of ul/ol lists.")
    blockquotes: list[str] = Field(default_factory=list, description="Texts of blockquotes.")
    code_blocks: list[str] = Field(
        default_factory=list,
        description="Texts of code blocks (pre/code).",
    )
    sections: list[Section] = Field(
        default_factory=list,
        description="Detected sections (e.g., Introduction, Conclusion).",
    )

    @property
    def word_count(self) -> int:
        """Calculate the word count from paragraphs and headings."""
        text = " ".join(self.headings + self.paragraphs)
        return len(text.split())
