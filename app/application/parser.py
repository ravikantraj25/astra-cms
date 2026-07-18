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

    # Extract title (prefer <title> tag, fallback to first <h1>)
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    else:
        h1 = soup.find("h1")
        if h1 and h1.text:
            title = h1.text.strip()

    # Extract meta description
    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_tag, Tag) and meta_tag.get("content"):
        meta_description = str(meta_tag.get("content")).strip()

    # Extract headings (h1-h6)
    headings = []
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if h.text:
            headings.append(h.text.strip())

    # Extract paragraphs
    paragraphs = []
    for p in soup.find_all("p"):
        if p.text:
            paragraphs.append(p.text.strip())

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
            links.append(
                Link(
                    href=str(href),
                    text=a.text.strip(),
                    title=str(a.get("title", "")),
                )
            )

    # Extract tables (raw HTML)
    tables = [str(table) for table in soup.find_all("table")]

    # Extract lists (raw HTML of ul/ol)
    lists = [str(lst) for lst in soup.find_all(["ul", "ol"])]

    # Extract blockquotes
    blockquotes = [bq.text.strip() for bq in soup.find_all("blockquote") if bq.text]

    # Extract code blocks (pre/code)
    code_blocks = []
    for pre in soup.find_all("pre"):
        code_blocks.append(pre.text.strip())
    # Also grab standalone code tags that are not inside pre
    for code in soup.find_all("code"):
        if code.parent and code.parent.name != "pre":
            code_blocks.append(code.text.strip())

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
