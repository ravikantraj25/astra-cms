"""Tests for the HTML parser module."""

from pathlib import Path

import pytest

from app.application.parser import parse_html_file, parse_html_string
from app.domain.article import Article


@pytest.fixture
def sample_html() -> str:
    """Return a sample HTML string."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Title from tag</title>
        <meta name="description" content="This is a test description.">
    </head>
    <body>
        <h1>Test Title</h1>
        <p>This is a paragraph with a <a href="https://example.com" title="Example">link</a>.</p>
        <p>Another paragraph.</p>
        <h2>Subheading</h2>
        <img src="test.jpg" alt="Test image" title="Test image title">
        <table>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </table>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <blockquote>This is a quote.</blockquote>
        <pre><code>print("hello")</code></pre>
        <code>inline code</code>
    </body>
    </html>
    """


def test_parse_html_string(sample_html: str) -> None:
    """It should correctly parse all required elements from the HTML string."""
    article = parse_html_string(sample_html)

    assert isinstance(article, Article)
    assert article.title == "Test Title"  # Prefer h1 over <title>
    assert article.meta_description == "This is a test description."
    assert article.headings == ["Test Title", "Subheading"]
    assert article.paragraphs == [
        "This is a paragraph with a link.",
        "Another paragraph.",
    ]
    assert len(article.images) == 1
    assert article.images[0].src == "test.jpg"
    assert article.images[0].alt == "Test image"
    assert article.images[0].title == "Test image title"

    assert len(article.links) == 1
    assert article.links[0].href == "https://example.com"
    assert article.links[0].text == "link"
    assert article.links[0].title == "Example"

    assert len(article.tables) == 1
    assert "<tr><td>Cell 1</td><td>Cell 2</td></tr>" in article.tables[0]

    assert len(article.lists) == 1
    assert "<li>Item 1</li>" in article.lists[0]

    assert article.blockquotes == ["This is a quote."]
    assert article.code_blocks == ['print("hello")', "inline code"]

    # Word count:
    # Headings: "Test Title Subheading" (4)
    # Paragraphs: "This is a paragraph with a link. Another paragraph." (9)
    # Total: 13
    assert article.word_count == 12


def test_parse_html_string_fallback_title() -> None:
    """It should fallback to the <title> if no h1 exists."""
    html = "<head><title>Fallback Title</title></head><body></body>"
    article = parse_html_string(html)
    assert article.title == "Fallback Title"


def test_parse_html_file(tmp_path: Path, sample_html: str) -> None:
    """It should parse a file and return the Article."""
    file_path = tmp_path / "test.html"
    file_path.write_text(sample_html, encoding="utf-8")

    article = parse_html_file(file_path)
    assert article.title == "Test Title"


def test_parse_html_file_not_found(tmp_path: Path) -> None:
    """It should raise FileNotFoundError if the file does not exist."""
    file_path = tmp_path / "does_not_exist.html"

    with pytest.raises(FileNotFoundError):
        parse_html_file(file_path)


def test_parse_html_string_wp_block_post_title() -> None:
    """It should prefer wp-block-post-title over title tag."""
    html = '<head><title>Tag Title</title></head><body><div class="wp-block-post-title">WP Block Title</div></body>'
    article = parse_html_string(html)
    assert article.title == "WP Block Title"


def test_parse_html_string_entry_title() -> None:
    """It should prefer entry-title over title tag."""
    html = '<head><title>Tag Title</title></head><body><h2 class="entry-title">Entry Title</h2></body>'
    article = parse_html_string(html)
    assert article.title == "Entry Title"


def test_parse_html_string_post_title() -> None:
    """It should prefer post-title over title tag."""
    html = '<head><title>Tag Title</title></head><body><span class="post-title">Post Title</span></body>'
    article = parse_html_string(html)
    assert article.title == "Post Title"
