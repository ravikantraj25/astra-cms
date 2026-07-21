"""Temporal analyzer."""

from datetime import datetime
from pydantic import BaseModel, Field

from app.domain.intelligence import (
    TemporalEntity,
    PolicyAction
)
from app.application.analyzers.base import BaseAnalyzer


class TemporalAnalysisResult(BaseModel):
    year_policy: PolicyAction
    date_policy: PolicyAction
    schedule_policy: PolicyAction
    entities: list[TemporalEntity] = Field(default_factory=list)
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class TemporalAnalyzer(BaseAnalyzer[TemporalAnalysisResult]):
    """Analyzes time-related elements."""
    
    def analyze(self, text: str) -> TemporalAnalysisResult:
        current_year = datetime.now().year
        prompt = f"""You are a specialized Temporal Analyzer AI.
Your ONLY responsibility is to analyze all time-related elements in the article.
Current year: {current_year}

Find ALL Years, Months, Dates, Deadlines, Exam dates, Application windows, Registration windows, Business hours, Opening hours, Closing hours, Festival dates, Schedules, Recurring events, Historical years, Future years, Past years, and Relative dates ("This year", "Next year").

Output ONLY valid JSON matching this schema:
{{
    "year_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "date_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "schedule_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "entities": [
        {{
            "entity_type": "Year" | "Month" | "Date" | "Deadline" | "Exam Date" | "Application Window" | "Registration Window" | "Business Hours" | "Opening Hours" | "Closing Hours" | "Festival Date" | "Schedule" | "Recurring Event" | "Historical Year" | "Future Year" | "Past Year" | "Relative Date",
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
        return self._generate_and_parse(prompt, TemporalAnalysisResult)
