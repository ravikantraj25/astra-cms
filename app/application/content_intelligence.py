"""Application service for Content Intelligence analysis."""

import logging
from bs4 import BeautifulSoup

from app.domain.ai import AIProvider
from app.domain.article import Article
from app.domain.intelligence import ArticleAnalysis, EditingPolicy

# Import specialized analyzers
from app.application.analyzers.classifier import ArticleClassifier
from app.application.analyzers.temporal import TemporalAnalyzer
from app.application.analyzers.historical import HistoricalAnalyzer
from app.application.analyzers.structural import StructuralAnalyzer
from app.application.analyzers.event import EventAnalyzer
from app.application.analyzers.risk import RiskAnalyzer
from app.application.analyzers.metadata import MetadataAnalyzer

logger = logging.getLogger(__name__)


class ContentIntelligenceAnalyzer:
    """Analyzes an article to produce structured content intelligence."""

    def __init__(self, ai_provider: AIProvider) -> None:
        """Initialize the analyzer with an AI provider."""
        self.ai_provider = ai_provider
        self.classifier = ArticleClassifier(ai_provider)
        self.temporal_analyzer = TemporalAnalyzer(ai_provider)
        self.historical_analyzer = HistoricalAnalyzer(ai_provider)
        self.structural_analyzer = StructuralAnalyzer(ai_provider)
        self.event_analyzer = EventAnalyzer(ai_provider)
        self.risk_analyzer = RiskAnalyzer(ai_provider)
        self.metadata_analyzer = MetadataAnalyzer(ai_provider)

    def analyze(self, article: Article) -> ArticleAnalysis:
        """Analyze the article and return structured intelligence.

        Args:
            article: The parsed Article domain model.

        Returns:
            A populated ArticleAnalysis object.
        """
        logger.info("Extracting raw text for content intelligence analysis.")
        
        # We strip HTML to reduce token usage and help the AI focus on semantic meaning
        soup = BeautifulSoup(article.raw_html, "html.parser")
        article_text = soup.get_text(separator="\n", strip=True)

        logger.info("Starting specialized analyzers...")
        
        # In a high-performance environment, these could be executed concurrently using asyncio.gather.
        # For simplicity and reliability in this synchronous context, we execute them sequentially.
        
        c_res = self.classifier.analyze(article_text)
        t_res = self.temporal_analyzer.analyze(article_text)
        h_res = self.historical_analyzer.analyze(article_text)
        s_res = self.structural_analyzer.analyze(article_text)
        e_res = self.event_analyzer.analyze(article_text)
        r_res = self.risk_analyzer.analyze(article_text)
        m_res = self.metadata_analyzer.analyze(article_text)
        
        logger.info("Aggregating specialized analysis into single EditingPolicy...")
        
        editing_policy = EditingPolicy(
            article_type=c_res.article_type,
            year_policy=t_res.year_policy,
            date_policy=t_res.date_policy,
            history_policy=h_res.history_policy,
            title_policy=m_res.title_policy,
            image_policy=s_res.image_policy,
            schema_policy=s_res.schema_policy,
            faq_policy=s_res.faq_policy,
            schedule_policy=t_res.schedule_policy,
            pricing_policy=m_res.pricing_policy,
            metadata_policy=m_res.metadata_policy,
            link_policy=s_res.link_policy,
            location_policy=e_res.location_policy,
            seo_policy=m_res.seo_policy
        )

        required_updates = list(set(
            c_res.required_updates + t_res.required_updates + h_res.required_updates +
            s_res.required_updates + e_res.required_updates + r_res.required_updates +
            m_res.required_updates
        ))

        forbidden_updates = list(set(
            c_res.forbidden_updates + t_res.forbidden_updates + h_res.forbidden_updates +
            s_res.forbidden_updates + e_res.forbidden_updates + r_res.forbidden_updates +
            m_res.forbidden_updates
        ))

        return ArticleAnalysis(
            editing_policy=editing_policy,
            strategy=c_res.strategy,
            freshness=c_res.freshness,
            required_updates=required_updates,
            forbidden_updates=forbidden_updates,
            temporal_entities=t_res.entities,
            historical_facts=h_res.facts,
            event_info=e_res.events,
            structural_analysis=s_res.elements,
            risks=r_res.risks
        )
