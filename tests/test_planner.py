"""Tests for the Update Planner logic."""

from __future__ import annotations

from app.application.planner import build_update_plan
from app.domain.article import Article, Section
from app.domain.plan import AnalysisResult


def test_build_update_plan_empty() -> None:
    """It should return an empty plan if no sections are present."""
    article = Article(title="No Sections")
    plan = build_update_plan(article, AnalysisResult())
    assert len(plan.actions) == 0


def test_build_update_plan_with_matches() -> None:
    """It should correctly identify sections to update based on analysis."""
    article = Article(
        title="Test Article",
        sections=[
            Section(
                name="FAQ",
                type="heading",
                astra_id="1",
                content="FAQ content",
            ),
            Section(
                name="History",
                type="heading",
                astra_id="2",
                content="History content",
            ),
            Section(
                name="Conclusion",
                type="heading",
                astra_id="3",
                content="End",
            ),
        ],
    )

    analysis = AnalysisResult(
        weaknesses=["The FAQ section is missing details."],
        suggestions=["Add more content to the History section."],
    )

    plan = build_update_plan(article, analysis)

    assert len(plan.actions) == 3

    faq_action = next(a for a in plan.actions if a.section == "FAQ")
    assert faq_action.action == "Update"
    assert faq_action.priority == "High"

    history_action = next(a for a in plan.actions if a.section == "History")
    assert history_action.action == "Update"
    assert history_action.priority == "High"

    conclusion_action = next(a for a in plan.actions if a.section == "Conclusion")
    assert conclusion_action.action == "Skip"
    assert conclusion_action.priority == "Low"


def test_build_update_plan_outdated_evergreen_and_confidences() -> None:
    """Should detect outdated info, skip evergreen sections, and assign exact confidence scores."""
    article = Article(
        title="Outdated vs Evergreen",
        sections=[
            Section(
                name="Statistics",
                type="heading",
                astra_id="1",
                content="Stats",
            ),
            Section(
                name="Foundations",
                type="heading",
                astra_id="2",
                content="Basics",
            ),
        ],
    )

    analysis = AnalysisResult(
        weaknesses=["The Statistics section contains outdated numbers from past years."],
        strengths=["Foundations section is evergreen and accurate."],
        confidence_scores={"Statistics": 96, "Foundations": 100},
    )

    plan = build_update_plan(article, analysis)
    assert len(plan.actions) == 2

    stats_action = next(a for a in plan.actions if a.section == "Statistics")
    assert stats_action.action == "Update"
    assert stats_action.confidence == 96
    assert "outdated" in stats_action.reason.lower()

    foundations_action = next(a for a in plan.actions if a.section == "Foundations")
    assert foundations_action.action == "Skip"
    assert foundations_action.confidence == 100
    assert "evergreen" in foundations_action.reason.lower()
