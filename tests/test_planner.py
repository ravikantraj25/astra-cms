"""Tests for the Update Planner."""

import json
from unittest.mock import MagicMock

import pytest

from app.domain.ai import AIProvider, AIError
from app.domain.article import Article, Section
from app.domain.plan import UpdatePlan, ActionType
from app.application.planner import Planner


@pytest.fixture
def mock_ai_provider():
    return MagicMock(spec=AIProvider)


@pytest.fixture
def dummy_article():
    return Article(
        raw_html="<h1>Dummy Title</h1><p data-astra-id='1'>Event runs in 2024</p>",
        title="Dummy Title",
        sections=[
            Section(name="Content", type="paragraph", astra_id="1", content="<p data-astra-id='1'>Event runs in 2024</p>")
        ]
    )


from app.domain.intelligence import ArticleAnalysis, ArticleType, ContentFreshness, UpdateStrategy, EditingPolicy, PolicyAction

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


def test_build_plan_success(mock_ai_provider, dummy_article, dummy_intelligence):
    """Test that a valid JSON response is parsed into an UpdatePlan."""
    valid_json = {
        "new_title": "Dummy Title 2025",
        "actions": [
            {
                "section_id": "1",
                "section": "Content",
                "action": "Update",
                "reason": "Needs new year",
                "confidence": 0.95,
                "fields_to_update": ["2024 to 2025"],
                "fields_to_preserve": [],
                "forbidden_changes": [],
                "required_entities": ["2025"],
                "expected_output": "Updated text"
            }
        ]
    }
    
    mock_ai_provider.generate.return_value = f"```json\n{json.dumps(valid_json)}\n```"
    
    planner = Planner(ai_provider=mock_ai_provider)
    result = planner.build_plan(dummy_article, dummy_intelligence)
    
    assert isinstance(result, UpdatePlan)
    assert result.new_title == "Dummy Title 2025"
    assert len(result.actions) == 1
    assert result.actions[0].section == "Content"
    assert result.actions[0].action == ActionType.UPDATE
    assert result.actions[0].confidence == 0.95


def test_build_plan_empty_sections(mock_ai_provider, dummy_intelligence):
    """Test that it handles articles with no sections without calling AI."""
    article_no_sections = Article(raw_html="<p>No astra tags</p>")
    
    planner = Planner(ai_provider=mock_ai_provider)
    result = planner.build_plan(article_no_sections, dummy_intelligence)
    
    assert isinstance(result, UpdatePlan)
    assert not result.actions
    mock_ai_provider.generate.assert_not_called()


def test_build_plan_retries_on_invalid_json(mock_ai_provider, dummy_article, dummy_intelligence):
    valid_json = {
        "new_title": None,
        "actions": [
            {
                "section_id": "1",
                "section": "Content",
                "action": "Skip",
                "reason": "No changes needed",
                "confidence": 1.0,
                "fields_to_update": [],
                "fields_to_preserve": [],
                "forbidden_changes": [],
                "required_entities": [],
                "expected_output": ""
            }
        ]
    }
    
    mock_ai_provider.generate.side_effect = [
        "Not json",
        json.dumps(valid_json)
    ]
    
    planner = Planner(ai_provider=mock_ai_provider)
    result = planner.build_plan(dummy_article, dummy_intelligence)
    
    assert result.actions[0].action == ActionType.SKIP
    assert mock_ai_provider.generate.call_count == 2


def test_build_plan_exhausts_retries(mock_ai_provider, dummy_article, dummy_intelligence):
    mock_ai_provider.generate.return_value = "Bad JSON"
    
    planner = Planner(ai_provider=mock_ai_provider)
    
    with pytest.raises(AIError, match="Failed to generate valid Update Plan"):
        planner.build_plan(dummy_article, dummy_intelligence)
        
    assert mock_ai_provider.generate.call_count == 4
