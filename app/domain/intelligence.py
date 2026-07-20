"""Domain models for content intelligence analysis."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ArticleType(str, Enum):
    """Broad classification of the article's core purpose."""
    FESTIVAL = "Festival"
    TEMPLE = "Temple"
    GOVERNMENT_SCHEME = "Government Scheme"
    ADMISSION = "Admission"
    UNIVERSITY = "University"
    EXAM = "Exam"
    NEWS = "News"
    RECIPE = "Recipe"
    TRAVEL = "Travel"
    HISTORY = "History"
    BIOGRAPHY = "Biography"
    PRODUCT_REVIEW = "Product Review"
    TECHNOLOGY = "Technology"
    TUTORIAL = "Tutorial"
    MEDICAL = "Medical"
    FINANCE = "Finance"
    SPORTS = "Sports"
    MOVIE = "Movie"
    ENTERTAINMENT = "Entertainment"
    STATIC_INFO = "Static Information"
    EVERGREEN = "Evergreen"
    ANNUAL_EVENT = "Annual Event"
    RECURRING_EVENT = "Recurring Event"
    LOCATION_GUIDE = "Location Guide"


class ContentFreshness(str, Enum):
    """The time-sensitivity or recurring nature of the content."""
    STATIC = "Static"
    EVERGREEN = "Evergreen"
    ANNUAL = "Annual"
    SEASONAL = "Seasonal"
    BREAKING_NEWS = "Breaking News"
    RECURRING_EVENT = "Recurring Event"
    HISTORICAL = "Historical"


class UpdatePolicy(str, Enum):
    """Actions the generator can take on a specific element."""
    KEEP = "KEEP"
    UPDATE = "UPDATE"
    REMOVE = "REMOVE"
    UNKNOWN = "UNKNOWN"


class StructuralPolicy(str, Enum):
    """How to treat structural elements."""
    MUST_STAY = "must stay"
    MAY_UPDATE = "may update"
    MUST_NEVER_CHANGE = "must never change"


class TemporalEntity(BaseModel):
    """A highly granular decision for an individual temporal element found in the text."""
    entity: str = Field(description="The specific temporal text (e.g., '2024', 'October 5', 'next year').")
    policy: UpdatePolicy = Field(description="The decision on how to handle this element.")
    reason: str = Field(description="Why this decision was made.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the decision. Mark UNKNOWN if low.")
    source_sentence: str = Field(description="The exact sentence containing this element.")


class HistoricalFact(BaseModel):
    """A fact that must never change."""
    fact: str = Field(description="The historical fact, timeline, biography, or cultural info.")
    reason: str = Field(description="Why it must never change.")


class EventInfo(BaseModel):
    """Extracted event information."""
    name: str = Field(description="Name of the event or celebration.")
    details: str = Field(description="Details such as schedule, venue, ticket booking, transport, etc.")


class StructuralElement(BaseModel):
    """Identified structural elements like headings, tables, schema, etc."""
    element_type: str = Field(description="Type of element (e.g. 'heading', 'table', 'schema', 'images').")
    policy: StructuralPolicy = Field(description="Whether it must stay, may update, or must never change.")


class RiskAssessment(BaseModel):
    """Identified risks associated with updating the article."""
    risk_type: str = Field(description="Type of risk (e.g., 'hallucination', 'date', 'pricing', 'legal', 'medical', 'financial').")
    description: str = Field(description="Description of the risk.")
    severity: str = Field(description="'High', 'Medium', or 'Low'")


class UpdateDecision(BaseModel):
    """High-level update decision for the overall article."""
    strategy: str = Field(description="E.g., 'Aggressive', 'Selective', 'Conservative', 'Preserve'")
    reason: str = Field(description="Reason for this strategy.")


class ArticleAnalysis(BaseModel):
    """The structured intelligence analysis for an article."""
    model_config = ConfigDict(extra="forbid")

    article_type: ArticleType = Field(description="The primary classification of the article.")
    freshness: ContentFreshness = Field(description="The freshness category.")
    decision: UpdateDecision = Field(description="Overall update strategy.")
    
    temporal_entities: list[TemporalEntity] = Field(
        default_factory=list,
        description="List of detected temporal elements (years, dates, schedules)."
    )
    historical_facts: list[HistoricalFact] = Field(
        default_factory=list,
        description="Facts that must never be changed."
    )
    event_info: list[EventInfo] = Field(
        default_factory=list,
        description="Extracted event details."
    )
    structural_analysis: list[StructuralElement] = Field(
        default_factory=list,
        description="Analysis of HTML structures."
    )
    risks: list[RiskAssessment] = Field(
        default_factory=list,
        description="Identified risks to be careful about."
    )
