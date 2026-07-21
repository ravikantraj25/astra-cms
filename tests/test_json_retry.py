import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.application.workflow import run_analysis_workflow
from app.infrastructure.wordpress.client import WordPressClient
from app.domain.ai import AIProvider, AIError
from app.infrastructure.wordpress.models import WPPost
from app.domain.intelligence import ArticleAnalysis, ArticleType, ContentFreshness, UpdateStrategy, EditingPolicy, PolicyAction

class MockProvider(AIProvider):
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def generate(self, prompt: str) -> str:
        response = self.responses[self.calls]
        self.calls += 1
        return response

@pytest.fixture
def dummy_intelligence():
    return ArticleAnalysis(
        strategy=UpdateStrategy.SELECTIVE,
        freshness=ContentFreshness.RECURRING_EVENT,
        editing_policy=EditingPolicy(
            article_type=ArticleType.ANNUAL_EVENT,
            year_policy=PolicyAction.UPDATE,
            date_policy=PolicyAction.UPDATE,
            history_policy=PolicyAction.KEEP,
            title_policy=PolicyAction.UPDATE,
            image_policy=PolicyAction.KEEP,
            schema_policy=PolicyAction.KEEP,
            faq_policy=PolicyAction.UPDATE,
            schedule_policy=PolicyAction.UPDATE,
            pricing_policy=PolicyAction.UPDATE,
            metadata_policy=PolicyAction.UPDATE,
            link_policy=PolicyAction.KEEP,
            location_policy=PolicyAction.KEEP,
            seo_policy=PolicyAction.UPDATE
        ),
        required_updates=[],
        forbidden_updates=[],
        temporal_entities=[],
        historical_facts=[],
        event_info=[],
        structural_analysis=[],
        risks=[],
    )

@patch("app.application.workflow.ContentIntelligenceAnalyzer")
def test_workflow_json_retry_success(mock_analyzer_cls, tmp_path: Path, dummy_intelligence):
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

    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.analyze.return_value = dummy_intelligence
    mock_analyzer_cls.return_value = mock_analyzer_instance

    valid_plan = '{"new_title": null, "actions": []}'
    
    # First two responses are invalid JSON, third is valid plan
    responses = [
        "Not JSON at all",
        "Still not JSON",
        valid_plan
    ]
    ai_provider = MockProvider(responses)

    artifacts = run_analysis_workflow(1, wp_client, ai_provider, tmp_path)
    
    assert ai_provider.calls == 3
    assert "plan" in artifacts

@patch("app.application.workflow.ContentIntelligenceAnalyzer")
def test_workflow_json_retry_failure(mock_analyzer_cls, tmp_path: Path, dummy_intelligence):
    wp_client = MagicMock(spec=WordPressClient)
    wp_client.__enter__.return_value = wp_client
    
    mock_post = MagicMock()
    mock_post.id = 1
    mock_post.title = "Test"
    mock_post.content_html = "<h1>Test</h1><h2>History</h2><p>Test</p>"
    
    mock_detail = MagicMock()
    mock_detail.post = mock_post
    wp_client.get_post.return_value = mock_detail

    mock_analyzer_instance = MagicMock()
    mock_analyzer_instance.analyze.return_value = dummy_intelligence
    mock_analyzer_cls.return_value = mock_analyzer_instance

    # All 4 responses are invalid JSON (attempt + 3 retries)
    responses = ["Invalid 1", "Invalid 2", "Invalid 3", "Invalid 4"]
    ai_provider = MockProvider(responses)

    with pytest.raises(AIError, match="Failed to generate valid Update Plan"):
        run_analysis_workflow(1, wp_client, ai_provider, tmp_path)
    
    assert ai_provider.calls == 4
