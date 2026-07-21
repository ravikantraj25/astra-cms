"""Domain models for content intelligence analysis."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class PolicyAction(str, Enum):
    """Explicit deterministic action for an element."""
    KEEP = "KEEP"
    UPDATE = "UPDATE"
    REMOVE = "REMOVE"
    IGNORE = "IGNORE"
    UNKNOWN = "UNKNOWN"


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


class TemporalEntityType(str, Enum):
    """Types of temporal entities."""
    YEAR = "Year"
    MONTH = "Month"
    DATE = "Date"
    DEADLINE = "Deadline"
    EXAM_DATE = "Exam Date"
    APPLICATION_WINDOW = "Application Window"
    REGISTRATION_WINDOW = "Registration Window"
    BUSINESS_HOURS = "Business Hours"
    OPENING_HOURS = "Opening Hours"
    CLOSING_HOURS = "Closing Hours"
    FESTIVAL_DATE = "Festival Date"
    SCHEDULE = "Schedule"
    RECURRING_EVENT = "Recurring Event"
    HISTORICAL_YEAR = "Historical Year"
    FUTURE_YEAR = "Future Year"
    PAST_YEAR = "Past Year"
    RELATIVE_DATE = "Relative Date"


class StructuralPolicyAction(str, Enum):
    """How to treat structural elements."""
    ALWAYS_PRESERVE = "Always Preserve"
    MAY_UPDATE = "May Update"
    NEVER_MODIFY = "Never Modify"


class RiskLevel(str, Enum):
    """Severity of a risk."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ContentFreshness(str, Enum):
    """The time-sensitivity or recurring nature of the content."""
    STATIC = "Static"
    EVERGREEN = "Evergreen"
    ANNUAL = "Annual"
    SEASONAL = "Seasonal"
    BREAKING_NEWS = "Breaking News"
    RECURRING_EVENT = "Recurring Event"
    HISTORICAL = "Historical"


class UpdateStrategy(str, Enum):
    """Overall strategy for the article."""
    AGGRESSIVE = "Aggressive"
    SELECTIVE = "Selective"
    CONSERVATIVE = "Conservative"
    PRESERVE = "Preserve"


class DecisionEvidence(BaseModel):
    """Evidence and reasoning for any important decision."""
    detected_value: str = Field(description="The exact text or concept found.")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0).")
    reason: str = Field(description="Why this decision was made.")
    evidence: str = Field(description="Supporting evidence.")
    source_section: str = Field(description="Name or ID of the section where this was found.")
    source_heading: str = Field(description="Closest heading above this text.")
    source_sentence: str = Field(description="The exact sentence or phrase from the text.")


class EditingPolicy(BaseModel):
    """Deterministic instructions for updating the article."""
    article_type: ArticleType = Field(description="Classification of the article.")
    year_policy: PolicyAction
    date_policy: PolicyAction
    history_policy: PolicyAction
    title_policy: PolicyAction
    image_policy: PolicyAction
    schema_policy: PolicyAction
    faq_policy: PolicyAction
    schedule_policy: PolicyAction
    pricing_policy: PolicyAction
    metadata_policy: PolicyAction
    link_policy: PolicyAction
    location_policy: PolicyAction
    seo_policy: PolicyAction


# -- Specialized Analysis Models --

class TemporalEntity(BaseModel):
    """A highly granular decision for an individual temporal element found in the text."""
    entity_type: TemporalEntityType
    policy: PolicyAction
    evidence: DecisionEvidence


class HistoricalFact(BaseModel):
    """A fact that must never change."""
    policy: PolicyAction = Field(default=PolicyAction.KEEP)
    evidence: DecisionEvidence


class EventInfo(BaseModel):
    """Extracted event information."""
    name: str = Field(description="Name of the event or celebration.")
    details: str = Field(description="Details such as schedule, venue, ticket booking, transport, etc.")
    evidence: DecisionEvidence


class StructuralElement(BaseModel):
    """Identified structural elements like headings, tables, schema, etc."""
    element_type: str = Field(description="Type of element (e.g. 'heading', 'table', 'schema', 'images').")
    policy: StructuralPolicyAction
    evidence: DecisionEvidence


class RiskAssessment(BaseModel):
    """Identified risks associated with updating the article."""
    risk_type: str = Field(description="Type of risk (e.g., 'hallucination', 'date', 'pricing').")
    severity: RiskLevel
    evidence: DecisionEvidence


class MetadataAnalysis(BaseModel):
    """Analysis of the article's title, SEO, schema, etc."""
    title_policy: PolicyAction
    seo_policy: PolicyAction
    schema_policy: PolicyAction
    evidence: DecisionEvidence


class ArticleAnalysis(BaseModel):
    """The structured intelligence analysis for an article, single source of truth."""
    model_config = ConfigDict(extra="forbid")

    # High level editing policy & strategy
    editing_policy: EditingPolicy
    strategy: UpdateStrategy = Field(description="Overall update strategy.")
    freshness: ContentFreshness = Field(description="The freshness category.")
    
    # Required vs Forbidden Updates
    required_updates: list[str] = Field(
        default_factory=list,
        description="Explicit changes the planner must include."
    )
    forbidden_updates: list[str] = Field(
        default_factory=list,
        description="Explicit changes the planner must forbid."
    )

    # Sub-analyses
    temporal_entities: list[TemporalEntity] = Field(default_factory=list)
    historical_facts: list[HistoricalFact] = Field(default_factory=list)
    event_info: list[EventInfo] = Field(default_factory=list)
    structural_analysis: list[StructuralElement] = Field(default_factory=list)
    risks: list[RiskAssessment] = Field(default_factory=list)
