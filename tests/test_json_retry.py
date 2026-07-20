import pytest
from pathlib import Path
from unittest.mock import MagicMock
from app.application.workflow import run_analysis_workflow
from app.infrastructure.wordpress.client import WordPressClient
from app.domain.ai import AIProvider, AIError
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
    mock_post.content_html = "<h1>Test</h1><h2>History</h2><p>Test</p>"
    
    mock_detail = MagicMock()
    mock_detail.post = mock_post
    wp_client.get_post.return_value = mock_detail

    valid_intel = '{"article_type": "News", "freshness": "Breaking News", "decision": {"strategy": "Selective", "reason": "test"}, "temporal_entities": [], "historical_facts": [], "event_info": [], "structural_analysis": [], "risks": []}'
    valid_plan = '{"new_title": null, "actions": []}'
    
    # First two responses are invalid JSON, third is valid intel, fourth is valid plan
    responses = [
        "Not JSON at all",
        "Still not JSON",
        valid_intel,
        valid_plan
    ]
    ai_provider = MockProvider(responses)

    artifacts = run_analysis_workflow(1, wp_client, ai_provider, tmp_path)
    
    assert ai_provider.calls == 4
    assert "intelligence" in artifacts
    assert "plan" in artifacts

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

    # All 4 responses are invalid JSON (attempt + 3 retries)
    responses = ["Invalid 1", "Invalid 2", "Invalid 3", "Invalid 4"]
    ai_provider = MockProvider(responses)

    with pytest.raises(AIError, match="Failed to generate valid Content Intelligence"):
        run_analysis_workflow(1, wp_client, ai_provider, tmp_path)
    
    assert ai_provider.calls == 4
