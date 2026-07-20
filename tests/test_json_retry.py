import pytest
from pathlib import Path
from unittest.mock import MagicMock
from app.application.workflow import run_analysis_workflow
from app.infrastructure.wordpress.client import WordPressClient
from app.domain.ai import AIProvider
from app.infrastructure.wordpress.models import WPPost

class MockProvider(AIProvider):
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def generate(self, prompt: str) -> str:
        response = self.responses[self.calls]
        self.calls += 1
        return response

def test_workflow_json_retry_success(tmp_path: Path):
    wp_client = MagicMock(spec=WordPressClient)
    # Mock context manager
    wp_client.__enter__.return_value = wp_client
    
    # Mock post
    mock_post = MagicMock(spec=WPPost)
    mock_post.id = 1
    mock_post.title = "Test"
    mock_post.content_html = "<h1>Test</h1>"
    
    mock_detail = MagicMock()
    mock_detail.post = mock_post
    wp_client.get_post.return_value = mock_detail

    # First two responses are invalid JSON, third is valid
    responses = [
        "Not JSON at all",
        "Still not JSON",
        '{"strengths": ["a"], "weaknesses": ["b"], "suggestions": ["c"], "confidence_scores": {"Test": 100}}'
    ]
    ai_provider = MockProvider(responses)

    artifacts = run_analysis_workflow(1, wp_client, ai_provider, tmp_path)
    
    assert ai_provider.calls == 3
    assert "analysis" in artifacts

def test_workflow_json_retry_failure(tmp_path: Path):
    wp_client = MagicMock(spec=WordPressClient)
    wp_client.__enter__.return_value = wp_client
    
    mock_post = MagicMock()
    mock_post.id = 1
    mock_post.title = "Test"
    mock_post.content_html = "<h1>Test</h1>"
    
    mock_detail = MagicMock()
    mock_detail.post = mock_post
    wp_client.get_post.return_value = mock_detail

    # All three responses are invalid JSON
    responses = ["Invalid 1", "Invalid 2", "Invalid 3"]
    ai_provider = MockProvider(responses)

    with pytest.raises(ValueError, match="AI failed to return valid JSON"):
        run_analysis_workflow(1, wp_client, ai_provider, tmp_path)
    
    assert ai_provider.calls == 3
