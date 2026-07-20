"""HTML parser using BeautifulSoup."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup, Tag

from app.domain.article import Article, Image, Link


def parse_html_file(file_path: str | Path) -> Article:
    """Parse a saved HTML file into a structured Article object.

    Args:
        file_path: The path to the HTML file.

    Returns:
        An :class:`Article` object containing the extracted information.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"HTML file not found: {path}")

    html_content = path.read_text(encoding="utf-8")
    return parse_html_string(html_content)


def parse_html_string(html: str) -> Article:
    """Parse an HTML string into a structured Article object.

    Args:
        html: The HTML string to parse.

    Returns:
        An :class:`Article` object containing the extracted information.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract title (prefer visible H1 or WP specific classes over <title> tag)
    title = ""
    title_tag = soup.find(
        lambda tag: tag.name == "h1" or 
        any(c in tag.get("class", []) for c in ["wp-block-post-title", "entry-title", "post-title"])
    )
    if title_tag:
        text = title_tag.get_text(" ", strip=True)
        if text:
            title = text

    if not title and soup.title and soup.title.string:
        text = soup.title.string.strip()
        if text:
            title = text

    # Extract meta description
    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_tag, Tag) and meta_tag.get("content"):
        text = str(meta_tag.get("content")).strip()
        if text:
            meta_description = text

    # Extract headings (h1-h6)
    headings = []
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = h.get_text(" ", strip=True)
        if text:
            headings.append(text)

    # Extract paragraphs
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)

    # Extract images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            images.append(
                Image(
                    src=str(src),
                    alt=str(img.get("alt", "")),
                    title=str(img.get("title", "")),
                )
            )

    # Extract links
    links = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if href:
            text = a.get_text(" ", strip=True)
            links.append(
                Link(
                    href=str(href),
                    text=text,
                    title=str(a.get("title", "")),
                )
            )

    # Extract tables (raw HTML)
    tables = [str(table) for table in soup.find_all("table")]

    # Extract lists (raw HTML of ul/ol)
    lists = [str(lst) for lst in soup.find_all(["ul", "ol"])]

    # Extract blockquotes
    blockquotes = []
    for bq in soup.find_all("blockquote"):
        text = bq.get_text(" ", strip=True)
        if text:
            blockquotes.append(text)

    # Extract code blocks (pre/code)
    code_blocks = []
    for pre in soup.find_all("pre"):
        text = pre.get_text("\n", strip=True)
        if text:
            code_blocks.append(text)
    # Also grab standalone code tags that are not inside pre
    for code in soup.find_all("code"):
        if code.parent and code.parent.name != "pre":
            text = code.get_text(" ", strip=True)
            if text:
                code_blocks.append(text)

    return Article(
        raw_html=html,
        title=title,
        meta_description=meta_description,
        headings=headings,
        paragraphs=paragraphs,
        images=images,
        links=links,
        tables=tables,
        lists=lists,
        blockquotes=blockquotes,
        code_blocks=code_blocks,
    )
