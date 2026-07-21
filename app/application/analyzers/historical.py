"""Historical analyzer."""

from pydantic import BaseModel, Field

from app.domain.intelligence import (
    HistoricalFact,
    PolicyAction
)
from app.application.analyzers.base import BaseAnalyzer


class HistoricalAnalysisResult(BaseModel):
    history_policy: PolicyAction
    facts: list[HistoricalFact] = Field(default_factory=list)
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class HistoricalAnalyzer(BaseAnalyzer[HistoricalAnalysisResult]):
    """Analyzes immutable historical facts."""
    
    def analyze(self, text: str) -> HistoricalAnalysisResult:
        prompt = f"""You are a specialized Historical Analyzer AI.
Your ONLY responsibility is to identify immutable historical facts, biographies, religious information, timelines, cultural foundations, and scientific facts.
These sections normally MUST be protected from modification.

Output ONLY valid JSON matching this schema:
{{
    "history_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "facts": [
        {{
            "policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
            "evidence": {{
                "detected_value": "<string>",
                "confidence": <float>,
                "reason": "<string>",
                "evidence": "<string>",
                "source_section": "<string>",
                "source_heading": "<string>",
                "source_sentence": "<string>"
            }}
        }}
    ],
    "required_updates": ["<explicit required update strings>"],
    "forbidden_updates": ["<explicit forbidden update strings>"]
}}

Article text to analyze:
{text}
"""
        return self._generate_and_parse(prompt, HistoricalAnalysisResult)
