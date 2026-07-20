"""Tests for the QualityValidator."""

from __future__ import annotations

from app.application.quality_validator import QualityValidator


def test_valid_html_update():
    """A perfectly valid update that preserves everything should pass."""
    original = (
        '<html><body><div id="main" class="content"><h1 class="wp-block-title">Hello</h1>'
        '<p>World</p><img src="a.jpg" /><a href="/internal">Link</a></div></body></html>'
    )
    updated = (
        '<html><body><div id="main" class="content"><h1 class="wp-block-title">Hello Updated</h1>'
        '<p>World and Friends</p><img src="a.jpg" /><a href="/internal">Link</a><a href="/new">New Link</a></div></body></html>'
    )
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "PASS"
    assert report.ready_to_publish
    assert report.word_diff == 4


def test_prompt_leakage():
    """Prompt leakage like 'here is the updated' should fail."""
    original = "<p>Original</p>"
    updated = "<p>Sure, here is the UPDATED HTML.</p><p>Original</p>"
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert report.prompt_leakage
    assert not report.ready_to_publish


def test_markdown_leakage():
    """Markdown code fences should fail."""
    original = "<p>Original</p>"
    updated = "```html\n<p>Original</p>\n```"
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert report.prompt_leakage
    assert not report.ready_to_publish


def test_dangerous_tags_script():
    """Adding a <script> tag should fail."""
    original = "<p>Original</p>"
    updated = "<p>Original</p><script>alert('xss')</script>"
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert report.dangerous_html
    assert not report.ready_to_publish


def test_dangerous_tags_inline_event():
    """Adding an inline event handler should fail."""
    original = "<p>Original</p>"
    updated = "<p onclick=\"alert('xss')\">Original</p>"
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert report.dangerous_html
    assert not report.ready_to_publish


def test_dangerous_tags_javascript_uri():
    """Adding a javascript: URI should fail."""
    original = "<p>Original</p>"
    updated = '<a href="javascript:alert(\'xss\')">Click</a>'
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert report.dangerous_html
    assert not report.ready_to_publish


def test_dangerous_tags_untrusted_iframe():
    """Adding an untrusted iframe should fail."""
    original = "<p>Original</p>"
    updated = '<iframe src="http://evil.com"></iframe>'
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert report.dangerous_html
    assert not report.ready_to_publish


def test_trusted_iframe_allowed():
    """A YouTube iframe should be allowed."""
    original = "<p>Original</p>"
    updated = '<p>Original</p><iframe src="https://youtube.com/embed/123"></iframe>'
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "PASS"
    assert report.ready_to_publish


def test_image_loss():
    """Removing an image should fail."""
    original = '<img src="a.jpg" /><img src="b.jpg" />'
    updated = '<img src="a.jpg" />'
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert not report.images_preserved
    assert not report.ready_to_publish


def test_table_loss():
    """Removing a table should fail."""
    original = "<table><tr><td>Hi</td></tr></table>"
    updated = "<p>Replaced table with text</p>"
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert not report.tables_preserved
    assert not report.ready_to_publish


def test_link_loss():
    """Removing an existing link should fail."""
    original = '<a href="/a">A</a><a href="/b">B</a>'
    updated = '<a href="/a">A</a>'
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert not report.links_preserved
    assert not report.ready_to_publish


def test_css_id_loss():
    """Removing classes and IDs should fail."""
    original = '<div id="main" class="wp-block wrapper"></div>'
    updated = '<div></div>'
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert not report.structure_preserved
    assert not report.ready_to_publish


def test_malformed_html():
    """HTML with no valid tags should fail."""
    original = "<p>Original</p>"
    updated = "Just some text, AI forgot all HTML tags."
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert not report.html_valid
    assert not report.ready_to_publish

def test_heading_loss():
    """Removing a heading should fail."""
    original = "<h1>Title</h1><h2>Subtitle</h2>"
    updated = "<h1>Title</h1>"
    
    report = QualityValidator.validate(original, updated)
    assert report.status == "FAIL"
    assert not report.structure_preserved
    assert not report.ready_to_publish
