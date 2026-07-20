"""Prompt builder for Content Intelligence analysis."""

from datetime import datetime


def build_intelligence_prompt(article_text: str) -> str:
    """Build the prompt for the Content Intelligence stage.

    Args:
        article_text: The stripped text of the article to analyze.

    Returns:
        The formatted prompt instructing the AI to produce ArticleAnalysis JSON.
    """
    current_year = datetime.now().year

    return f"""You are an expert Content Strategy AI and Software Architect.

Your task is to analyze the following article content and produce a detailed Content Intelligence report. This report will guide downstream systems on exactly how to update the article for the current year ({current_year}).

You must output a strictly formatted JSON object matching this schema:

{{
  "article_type": "Festival" | "Temple" | "Government Scheme" | "Admission" | "University" | "Exam" | "News" | "Recipe" | "Travel" | "History" | "Biography" | "Product Review" | "Technology" | "Tutorial" | "Medical" | "Finance" | "Sports" | "Movie" | "Entertainment" | "Static Information" | "Evergreen" | "Annual Event" | "Recurring Event" | "Location Guide",
  "freshness": "Static" | "Evergreen" | "Annual" | "Seasonal" | "Breaking News" | "Recurring Event" | "Historical",
  "decision": {{
    "strategy": "Aggressive" | "Selective" | "Conservative" | "Preserve",
    "reason": "<string>"
  }},
  "temporal_entities": [
    {{
      "entity": "<string>",
      "policy": "KEEP" | "UPDATE" | "REMOVE" | "UNKNOWN",
      "reason": "<string>",
      "confidence": <float between 0.0 and 1.0>,
      "source_sentence": "<string>"
    }}
  ],
  "historical_facts": [
    {{
      "fact": "<string>",
      "reason": "<string>"
    }}
  ],
  "event_info": [
    {{
      "name": "<string>",
      "details": "<string>"
    }}
  ],
  "structural_analysis": [
    {{
      "element_type": "<string>",
      "policy": "must stay" | "may update" | "must never change"
    }}
  ],
  "risks": [
    {{
      "risk_type": "<string>",
      "description": "<string>",
      "severity": "High" | "Medium" | "Low"
    }}
  ]
}}

### Instructions for fields:
1. **article_type**: Classify the article into one of the exact string categories.
2. **freshness**: Determine how time-sensitive the content is.
3. **decision**: High-level update strategy and rationale.
4. **temporal_entities**: Find ALL years, dates, months, deadlines, registration windows, opening hours, ticket timings, etc. Decide KEEP, UPDATE, REMOVE, or UNKNOWN.
5. **historical_facts**: Identify historical facts, timelines, biographies, culture, and religion which MUST NEVER change.
6. **event_info**: Identify event names, celebrations, schedules, ceremonies, venue, transport.
7. **structural_analysis**: Detect headings, tables, FAQ, images, captions, schema, links, shortcodes, lists. Assign policy.
8. **risks**: Identify hallucination risk, date risk, pricing risk, schedule risk, location risk, legal risk, medical risk, financial risk.

### Output Requirements:
- Output ONLY valid JSON.
- Do NOT wrap the JSON in Markdown formatting (no ```json ... ```).
- Do NOT include any explanations or conversational text.

### Article Text:
{article_text}
"""
