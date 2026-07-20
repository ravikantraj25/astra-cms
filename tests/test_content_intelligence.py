"""Tests for the Content Intelligence Analyzer."""

import json
from unittest.mock import MagicMock

import pytest

from app.domain.ai import AIProvider, AIError
from app.domain.article import Article
from app.domain.intelligence import ArticleType, ContentFreshness, ArticleAnalysis, UpdatePolicy
from app.application.content_intelligence import ContentIntelligenceAnalyzer


@pytest.fixture
def mock_ai_provider():
    return MagicMock(spec=AIProvider)


@pytest.fixture
def dummy_article():
    return Article(raw_html="<h1>Dummy Title</h1><p>Event runs in 2024</p>")


def test_analyze_success(mock_ai_provider, dummy_article):
    """Test that a valid JSON response is correctly parsed into ArticleAnalysis."""
    valid_json = {
        "article_type": "Annual Event",
        "freshness": "Recurring Event",
        "decision": {
            "strategy": "Selective",
            "reason": "Because it's an annual event."
        },
        "temporal_entities": [
            {
                "entity": "2024",
                "policy": "UPDATE",
                "reason": "Needs to be updated to current year",
                "confidence": 0.99,
                "source_sentence": "Event runs in 2024"
            }
        ],
        "historical_facts": [],
        "event_info": [],
        "structural_analysis": [],
        "risks": []
    }
    
    # Wrap in markdown just to ensure markdown stripping works
    mock_ai_provider.generate.return_value = f"```json\n{json.dumps(valid_json)}\n```"
    
    analyzer = ContentIntelligenceAnalyzer(ai_provider=mock_ai_provider)
    result = analyzer.analyze(dummy_article)
    
    assert isinstance(result, ArticleAnalysis)
    assert result.article_type == ArticleType.ANNUAL_EVENT
    assert result.freshness == ContentFreshness.RECURRING_EVENT
    assert result.decision.strategy == "Selective"
    
    assert len(result.temporal_entities) == 1
    assert result.temporal_entities[0].entity == "2024"
    assert result.temporal_entities[0].policy == UpdatePolicy.UPDATE
    assert result.temporal_entities[0].confidence == 0.99
    
    # Ensure AIProvider was called exactly once
    mock_ai_provider.generate.assert_called_once()
    

def test_analyze_retries_on_invalid_json(mock_ai_provider, dummy_article):
    """Test that the analyzer retries when the AI returns malformed JSON."""
    valid_json = {
        "article_type": "News",
        "freshness": "Breaking News",
        "decision": {
            "strategy": "Aggressive",
            "reason": "Because it's breaking news."
        },
        "temporal_entities": [],
        "historical_facts": [],
        "event_info": [],
        "structural_analysis": [],
        "risks": []
    }
    
    mock_ai_provider.generate.side_effect = [
        "This is not JSON at all.",
        '{"missing_closing_brace": true',
        json.dumps(valid_json)
    ]
    
    analyzer = ContentIntelligenceAnalyzer(ai_provider=mock_ai_provider)
    result = analyzer.analyze(dummy_article)
    
    assert result.article_type == ArticleType.NEWS
    assert mock_ai_provider.generate.call_count == 3


def test_analyze_retries_on_validation_error(mock_ai_provider, dummy_article):
    """Test that the analyzer retries when the AI returns JSON that fails Pydantic validation."""
    invalid_schema_json = {
        # Missing required fields like category and update_rules
        "confidence": 0.9,
    }
    
    valid_json = {
        "article_type": "Evergreen",
        "freshness": "Evergreen",
        "decision": {
            "strategy": "Preserve",
            "reason": "Because it's evergreen content."
        },
        "temporal_entities": [],
        "historical_facts": [],
        "event_info": [],
        "structural_analysis": [],
        "risks": []
    }
    
    mock_ai_provider.generate.side_effect = [
        json.dumps(invalid_schema_json),
        json.dumps(valid_json)
    ]
    
    analyzer = ContentIntelligenceAnalyzer(ai_provider=mock_ai_provider)
    result = analyzer.analyze(dummy_article)
    
    assert result.article_type == ArticleType.EVERGREEN
    assert mock_ai_provider.generate.call_count == 2


def test_analyze_exhausts_retries(mock_ai_provider, dummy_article):
    """Test that the analyzer raises an AIError after exhausting retries."""
    mock_ai_provider.generate.return_value = "Not JSON"
    
    analyzer = ContentIntelligenceAnalyzer(ai_provider=mock_ai_provider)
    
    with pytest.raises(AIError, match="Failed to generate valid Content Intelligence"):
        analyzer.analyze(dummy_article)
        
    # Initial attempt + 3 retries = 4 calls total
    assert mock_ai_provider.generate.call_count == 4
