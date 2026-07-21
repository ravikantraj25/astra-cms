"""Risk analyzer."""

from pydantic import BaseModel, Field

from app.domain.intelligence import (
    RiskAssessment
)
from app.application.analyzers.base import BaseAnalyzer


class RiskAnalysisResult(BaseModel):
    risks: list[RiskAssessment] = Field(default_factory=list)
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class RiskAnalyzer(BaseAnalyzer[RiskAnalysisResult]):
    """Analyzes risks associated with updating the article."""
    
    def analyze(self, text: str) -> RiskAnalysisResult:
        prompt = f"""You are a specialized Risk Analyzer AI.
Your ONLY responsibility is to identify risks to be careful about when modifying this text: Hallucination risk, Date risk, Pricing risk, Schedule risk, Location risk, Legal risk, Medical risk, Financial risk.

Output ONLY valid JSON matching this schema:
{{
    "risks": [
        {{
            "risk_type": "<string>",
            "severity": "High" | "Medium" | "Low",
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
        return self._generate_and_parse(prompt, RiskAnalysisResult)
