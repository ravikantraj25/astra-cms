"""Structural analyzer."""

from pydantic import BaseModel, Field

from app.domain.intelligence import (
    StructuralElement,
    PolicyAction
)
from app.application.analyzers.base import BaseAnalyzer


class StructuralAnalysisResult(BaseModel):
    image_policy: PolicyAction
    schema_policy: PolicyAction
    faq_policy: PolicyAction
    link_policy: PolicyAction
    elements: list[StructuralElement] = Field(default_factory=list)
    required_updates: list[str] = Field(default_factory=list)
    forbidden_updates: list[str] = Field(default_factory=list)


class StructuralAnalyzer(BaseAnalyzer[StructuralAnalysisResult]):
    """Analyzes structural elements."""
    
    def analyze(self, text: str) -> StructuralAnalysisResult:
        prompt = f"""You are a specialized Structural Analyzer AI.
Your ONLY responsibility is to classify structural elements: Images, Tables, Links, Schema, FAQ, Captions, Lists, Embeds, Shortcodes, Headings.
Determine for each whether it should Always Preserve, May Update, or Never Modify.

Output ONLY valid JSON matching this schema:
{{
    "image_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "schema_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "faq_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "link_policy": "KEEP" | "UPDATE" | "REMOVE" | "IGNORE" | "UNKNOWN",
    "elements": [
        {{
            "element_type": "<string e.g. heading, table, schema, images>",
            "policy": "Always Preserve" | "May Update" | "Never Modify",
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
        return self._generate_and_parse(prompt, StructuralAnalysisResult)
