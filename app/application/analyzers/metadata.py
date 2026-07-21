"""Metadata analyzer."""

from pydantic import BaseModel, Field

from app.domain.intelligence import (
    PolicyAction,
    DecisionEvidence
)
from app.application.analyzers.base import BaseAnalyzer


class MetadataAnalysisResult(BaseModel):
    title_policy: PolicyAction
    seo_policy: PolicyAction
    pricing_policy: PolicyAction
    metadata_policy: PolicyAction
    evidence: DecisionEvidence
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class MetadataAnalyzer(BaseAnalyzer[MetadataAnalysisResult]):
    """Analyzes metadata, SEO, title, and pricing rules."""
    
    def analyze(self, text: str) -> MetadataAnalysisResult:
        prompt = f"""You are a specialized Metadata Analyzer AI.
Your ONLY responsibility is to evaluate policies for the title, SEO, general metadata, and pricing mentioned in the text.

Output ONLY valid JSON matching this schema:
{{
    "title_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "seo_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "pricing_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "metadata_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "evidence": {{
        "detected_value": "<string>",
        "confidence": <float>,
        "reason": "<string>",
        "evidence": "<string>",
        "source_section": "<string>",
        "source_heading": "<string>",
        "source_sentence": "<string>"
    }},
    "required_updates": ["<explicit required update strings>"],
    "forbidden_updates": ["<explicit forbidden update strings>"]
}}

Article text to analyze:
{text}
"""
        return self._generate_and_parse(prompt, MetadataAnalysisResult)
