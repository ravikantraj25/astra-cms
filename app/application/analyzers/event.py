"""Event analyzer."""

from pydantic import BaseModel, Field

from app.domain.intelligence import (
    EventInfo,
    PolicyAction
)
from app.application.analyzers.base import BaseAnalyzer


class EventAnalysisResult(BaseModel):
    location_policy: PolicyAction
    events: list[EventInfo] = Field(default_factory=list)
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class EventAnalyzer(BaseAnalyzer[EventAnalysisResult]):
    """Analyzes events and related information."""
    
    def analyze(self, text: str) -> EventAnalysisResult:
        prompt = f"""You are a specialized Event Analyzer AI.
Your ONLY responsibility is to extract event information, names, celebrations, schedules, ceremonies, venue, and transport details.

Output ONLY valid JSON matching this schema:
{{
    "location_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "events": [
        {{
            "name": "<string>",
            "details": "<string>",
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
        return self._generate_and_parse(prompt, EventAnalysisResult)
