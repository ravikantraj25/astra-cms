"""Classifier analyzer."""

from pydantic import BaseModel, Field

from app.domain.intelligence import (
    ArticleType, 
    ContentFreshness, 
    UpdateStrategy,
    DecisionEvidence,
    PolicyAction
)
from app.application.analyzers.base import BaseAnalyzer


class ClassifierResult(BaseModel):
    article_type: ArticleType
    freshness: ContentFreshness
    strategy: UpdateStrategy
    article_type_evidence: DecisionEvidence
    freshness_evidence: DecisionEvidence
    strategy_evidence: DecisionEvidence
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class ArticleClassifier(BaseAnalyzer[ClassifierResult]):
    """Analyzes the core type, freshness, and overall strategy of the article."""
    
    def analyze(self, text: str) -> ClassifierResult:
        prompt = f"""You are a specialized Article Classifier AI.
Your ONLY responsibility is to determine the article type, freshness, and high-level update strategy.

Output ONLY valid JSON matching this schema:
{{
    "article_type": "Festival" | "Temple" | "Government Scheme" | "Admission" | "News" | "Recipe" | "Travel" | "History" | "Biography" | "Product Review" | "Technology" | "Tutorial" | "Medical" | "Finance" | "Sports" | "Movie" | "Entertainment" | "Static Information" | "Evergreen" | "Annual Event" | "Recurring Event" | "Location Guide",
    "freshness": "Static" | "Evergreen" | "Annual" | "Seasonal" | "Breaking News" | "Recurring Event" | "Historical",
    "strategy": "Aggressive" | "Selective" | "Conservative" | "Preserve",
    "article_type_evidence": {{
        "detected_value": "<string>",
        "confidence": <float>,
        "reason": "<string>",
        "evidence": "<string>",
        "source_section": "<string>",
        "source_heading": "<string>",
        "source_sentence": "<string>"
    }},
    "freshness_evidence": {{ ... same evidence fields ... }},
    "strategy_evidence": {{ ... same evidence fields ... }},
    "required_updates": ["<explicit required update strings>"],
    "forbidden_updates": ["<explicit forbidden update strings>"]
}}

Article text to analyze:
{text}
"""
        return self._generate_and_parse(prompt, ClassifierResult)
