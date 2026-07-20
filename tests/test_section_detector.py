"""Tests for the section detection module."""

from app.application.parser import parse_html_string
from app.application.section_detector import detect_sections


def test_detect_sections() -> None:
    """It should correctly detect sections from a parsed article."""
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>Main Title</h1>
        <p>This is the introduction.</p>
        <p>It continues here.</p>

        <h2>Table of Contents</h2>
        <ul><li>Intro</li><li>History</li></ul>

        <h2>History</h2>
        <p>Founded in 2026.</p>
        
        <h2>Venue</h2>
        <p>New York City</p>

        <img src="test.jpg" alt="test image">
        <video src="video.mp4"></video>

        <a href="https://example.com">External Link</a>
        <a href="/about">Internal Link</a>

        <h2>Conclusion</h2>
        <p>The end.</p>
        <p>Aug 15, 2026 was a great day.</p>
    </body>
    </html>
    """
    article = parse_html_string(html)
    article = detect_sections(article)

    # Verify Introduction
    intro = next((s for s in article.sections if s.type == "introduction"), None)
    assert intro is not None
    assert "This is the introduction." in intro.content

    # Verify Table of Contents
    toc = next((s for s in article.sections if s.type == "table_of_contents"), None)
    assert toc is not None
    assert "Table of Contents" in toc.name

    # Verify History
    history = next((s for s in article.sections if s.type == "history"), None)
    assert history is not None
    assert "Founded in 2026" in history.content

    # Verify Venue
    venue = next((s for s in article.sections if s.type == "venue"), None)
    assert venue is not None

    # Verify Conclusion
    conclusion = next((s for s in article.sections if s.type == "conclusion"), None)
    assert conclusion is not None

    # Verify Date Section
    date_section = next((s for s in article.sections if s.type == "date_section"), None)
    assert date_section is not None
    assert "Aug 15, 2026" in date_section.content

    # Verify Media
    image = next((s for s in article.sections if s.type == "image"), None)
    assert image is not None
    assert "test.jpg" in image.content

    video = next((s for s in article.sections if s.type == "video"), None)
    assert video is not None
    assert "video.mp4" in video.content

    # Verify Links
    ext_link = next((s for s in article.sections if s.type == "external_link"), None)
    assert ext_link is not None
    assert "example.com" in ext_link.content

    int_link = next((s for s in article.sections if s.type == "internal_link"), None)
    assert int_link is not None
    assert "/about" in int_link.content
