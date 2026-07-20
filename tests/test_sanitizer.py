import pytest
from app.application.generator import sanitize_html

def test_sanitize_html_removes_scripts():
    html = '<p>Hello</p><script>alert("XSS")</script>'
    safe = sanitize_html(html)
    assert "<script" not in safe
    assert "<p>Hello</p>" in safe

def test_sanitize_html_removes_on_attributes():
    html = '<button onclick="steal_cookies()">Click Me</button>'
    safe = sanitize_html(html)
    assert "onclick" not in safe
    assert "<button>Click Me</button>" in safe

def test_sanitize_html_removes_javascript_hrefs():
    html = '<a href="javascript:alert(1)">Click</a>'
    safe = sanitize_html(html)
    assert "javascript:" not in safe

def test_sanitize_html_preserves_safe_elements():
    html = '<h1>Title</h1><p class="content">Text <a href="https://example.com" target="_blank">Link</a></p><img src="test.jpg" alt="Test">'
    safe = sanitize_html(html)
    assert "<h1>Title</h1>" in safe
    assert 'class="content"' in safe
    assert 'href="https://example.com"' in safe
    assert 'src="test.jpg"' in safe
    assert 'alt="Test"' in safe

def test_sanitize_html_preserves_youtube_iframes():
    html = '<iframe src="https://www.youtube.com/embed/123"></iframe><iframe src="http://evil.com/hack"></iframe>'
    safe = sanitize_html(html)
    assert "youtube.com" in safe
    assert "evil.com" not in safe
