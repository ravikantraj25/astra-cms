"""Tests for the Content Intelligence Analyzer."""

import pytest
from unittest.mock import MagicMock

from app.domain.ai import AIProvider
from app.domain.article import Article
from app.domain.intelligence import (
    ArticleType, 
    ContentFreshness, 
    ArticleAnalysis, 
    UpdateStrategy,
    PolicyAction,
    EditingPolicy
)
from app.application.content_intelligence import ContentIntelligenceAnalyzer
from app.application.analyzers.classifier import ClassifierResult
from app.application.analyzers.temporal import TemporalAnalysisResult
from app.application.analyzers.historical import HistoricalAnalysisResult
from app.application.analyzers.structural import StructuralAnalysisResult
from app.application.analyzers.event import EventAnalysisResult
from app.application.analyzers.risk import RiskAnalysisResult
from app.application.analyzers.metadata import MetadataAnalysisResult


@pytest.fixture
def mock_ai_provider():
    return MagicMock(spec=AIProvider)


@pytest.fixture
def dummy_article():
    return Article(raw_html="<h1>Dummy Title</h1><p>Event runs in 2024</p>")


from app.domain.intelligence import DecisionEvidence

def test_analyze_orchestrator(mock_ai_provider, dummy_article):
    """Test that the orchestrator correctly aggregates the results from all specialized analyzers."""
    analyzer = ContentIntelligenceAnalyzer(ai_provider=mock_ai_provider)
    
    mock_evidence = DecisionEvidence(
        detected_value="test",
        confidence=1.0,
        reason="reason",
        evidence="evidence",
        source_section="s",
        source_heading="h",
        source_sentence="ss"
    )

    # Mock each analyzer's analyze method
    analyzer.classifier.analyze = MagicMock(return_value=ClassifierResult(
        article_type=ArticleType.ANNUAL_EVENT,
        freshness=ContentFreshness.RECURRING_EVENT,
        strategy=UpdateStrategy.SELECTIVE,
        article_type_evidence=mock_evidence,
        freshness_evidence=mock_evidence,
        strategy_evidence=mock_evidence,
        required_updates=["Update year to 2026"],
        forbidden_updates=[]
    ))
    
    analyzer.temporal_analyzer.analyze = MagicMock(return_value=TemporalAnalysisResult(
        year_policy=PolicyAction.UPDATE,
        date_policy=PolicyAction.UPDATE,
        schedule_policy=PolicyAction.KEEP,
        entities=[],
        required_updates=[],
        forbidden_updates=[]
    ))
    
    analyzer.historical_analyzer.analyze = MagicMock(return_value=HistoricalAnalysisResult(
        history_policy=PolicyAction.KEEP,
        facts=[],
        required_updates=[],
        forbidden_updates=["Do not change history"]
    ))
    
    analyzer.structural_analyzer.analyze = MagicMock(return_value=StructuralAnalysisResult(
        image_policy=PolicyAction.KEEP,
        schema_policy=PolicyAction.KEEP,
        faq_policy=PolicyAction.UPDATE,
        link_policy=PolicyAction.KEEP,
        elements=[],
        required_updates=[],
        forbidden_updates=[]
    ))
    
    analyzer.event_analyzer.analyze = MagicMock(return_value=EventAnalysisResult(
        location_policy=PolicyAction.KEEP,
        events=[],
        required_updates=[],
        forbidden_updates=[]
    ))
    
    analyzer.risk_analyzer.analyze = MagicMock(return_value=RiskAnalysisResult(
        risks=[],
        required_updates=[],
        forbidden_updates=[]
    ))
    
    analyzer.metadata_analyzer.analyze = MagicMock(return_value=MetadataAnalysisResult(
        title_policy=PolicyAction.UPDATE,
        seo_policy=PolicyAction.UPDATE,
        pricing_policy=PolicyAction.KEEP,
        metadata_policy=PolicyAction.UPDATE,
        evidence=mock_evidence,
        required_updates=["Update SEO"],
        forbidden_updates=[]
    ))
    
    result = analyzer.analyze(dummy_article)
    
    assert isinstance(result, ArticleAnalysis)
    assert result.strategy == UpdateStrategy.SELECTIVE
    assert result.freshness == ContentFreshness.RECURRING_EVENT
    
    assert result.editing_policy.article_type == ArticleType.ANNUAL_EVENT
    assert result.editing_policy.year_policy == PolicyAction.UPDATE
    assert result.editing_policy.history_policy == PolicyAction.KEEP
    assert result.editing_policy.title_policy == PolicyAction.UPDATE
    
    assert "Update year to 2026" in result.required_updates
    assert "Update SEO" in result.required_updates
    assert "Do not change history" in result.forbidden_updates
