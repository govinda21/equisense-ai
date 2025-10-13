"""
Test suite for verifying the enhancements to the stock analysis system
"""
import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, List

# Test imports
from app.graph.state import ResearchState
from app.graph.nodes.synthesis_multi import (
    AdaptiveScoring,
    ExplainableScore,
    _calculate_enhanced_score,
    create_comparative_analysis
)
from app.tools.data_federation import (
    DataFederation,
    YahooFinanceSource,
    CurrencyConverter
)
from app.tools.financial_nlp import (
    FinancialSentimentAnalyzer,
    EntityRecognizer,
    NewsCredibilityScorer,
    FinancialTextSummarizer
)
from app.tools.realtime_data import (
    MarketEvent,
    EventTrigger,
    EventDrivenAnalyzer,
    MarketDataAggregator
)


class TestAdaptiveScoring:
    """Test adaptive scoring system"""
    
    def test_sector_weights(self):
        """Test that sector-specific weights are applied correctly"""
        
        # Technology sector weights
        tech_weights = AdaptiveScoring.get_adaptive_weights("Technology", "bull")
        assert "technicals" in tech_weights
        assert "growth" in tech_weights
        assert abs(sum(tech_weights.values()) - 1.0) < 0.01  # Weights sum to 1
        
        # Financial sector weights
        fin_weights = AdaptiveScoring.get_adaptive_weights("Financial Services", "bear")
        assert fin_weights["fundamentals"] > tech_weights["fundamentals"]  # Financials prioritize fundamentals
        
    def test_regime_adjustments(self):
        """Test that market regime adjusts weights appropriately"""
        
        bull_weights = AdaptiveScoring.get_adaptive_weights("Technology", "bull")
        bear_weights = AdaptiveScoring.get_adaptive_weights("Technology", "bear")
        
        # In bear market, valuation becomes more important
        assert bear_weights.get("valuation", 0) >= bull_weights.get("valuation", 0)
        
        # In bull market, growth is more important
        assert bull_weights.get("growth", 0) >= bear_weights.get("growth", 0)
    
    def test_explainable_score(self):
        """Test explainability tracking"""
        
        explainer = ExplainableScore()
        explainer.add_component("technicals", 0.7, 0.3, 0.9)
        explainer.add_component("fundamentals", 0.6, 0.4, 0.8)
        
        total = explainer.get_total_score()
        assert 0 <= total <= 1
        
        explanation = explainer.get_explanation()
        assert "contributions" in explanation
        assert "components" in explanation
        assert len(explanation["components"]) == 2


class TestDataFederation:
    """Test multi-source data federation"""
    
    @pytest.mark.asyncio
    async def test_data_reconciliation(self):
        """Test that data from multiple sources is reconciled correctly"""
        
        federation = DataFederation()
        
        # Mock results from different sources
        results = [
            (YahooFinanceSource(), {
                "pe_ratio": 25.5,
                "market_cap": 1000000000,
                "source": "YahooFinance"
            }),
            (YahooFinanceSource(), {
                "pe_ratio": 26.0,
                "market_cap": 1050000000,
                "source": "AlphaVantage"
            })
        ]
        
        # Test reconciliation
        reconciled = federation._reconcile_fundamental_data(results)
        
        # Should have averaged the values
        assert "pe_ratio" in reconciled
        assert 25.0 <= reconciled["pe_ratio"] <= 26.5
        
        # Should have confidence score for disagreement
        if "pe_ratio_confidence" in reconciled:
            assert 0 <= reconciled["pe_ratio_confidence"] <= 1
    
    @pytest.mark.asyncio
    async def test_currency_conversion(self):
        """Test currency conversion functionality"""
        
        converter = CurrencyConverter()
        
        # Test USD to EUR conversion (using mock rates)
        converter.rates_cache = {"USD": 1.0, "EUR": 0.85}
        converter.last_update = datetime.utcnow()
        
        eur_amount = await converter.convert(100, "USD", "EUR")
        assert eur_amount == 85.0
        
        # Test cross-currency conversion
        converter.rates_cache = {"USD": 1.0, "EUR": 0.85, "GBP": 0.73}
        gbp_amount = await converter.convert(100, "EUR", "GBP")
        assert gbp_amount > 0  # Should convert via USD
    
    @pytest.mark.asyncio
    async def test_financial_normalization(self):
        """Test financial data normalization to common currency"""
        
        converter = CurrencyConverter()
        converter.rates_cache = {"USD": 1.0, "INR": 75.0}
        converter.last_update = datetime.utcnow()
        
        data = {
            "market_cap": 75000000,  # 75M INR
            "revenue": 10000000,  # 10M INR
            "pe_ratio": 15.5  # Ratios shouldn't be converted
        }
        
        normalized = await converter.normalize_financials(data, "INR", "USD")
        
        assert normalized["market_cap"] == 1000000  # 1M USD
        assert normalized["revenue"] == 10000000 / 75  # Converted to USD
        assert normalized["pe_ratio"] == 15.5  # Unchanged
        assert normalized["normalized_currency"] == "USD"


class TestFinancialNLP:
    """Test enhanced NLP capabilities"""
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis(self):
        """Test financial sentiment analysis"""
        
        analyzer = FinancialSentimentAnalyzer()
        
        positive_texts = [
            "Company beats earnings expectations with strong Q3 results",
            "Revenue growth accelerates, margins expand significantly"
        ]
        
        negative_texts = [
            "Company misses earnings, cuts guidance for full year",
            "Declining revenue and mounting losses concern investors"
        ]
        
        # Test positive sentiment
        pos_result = await analyzer.analyze_sentiment(positive_texts)
        assert pos_result["score"] > 0.5
        assert pos_result["label"] in ["positive", "neutral"]
        
        # Test negative sentiment
        neg_result = await analyzer.analyze_sentiment(negative_texts)
        assert neg_result["score"] <= 0.5
        assert neg_result["label"] in ["negative", "neutral"]
    
    @pytest.mark.asyncio
    async def test_entity_extraction(self):
        """Test financial entity extraction"""
        
        recognizer = EntityRecognizer()
        
        text = """
        Apple Inc. (AAPL) reported Q3 2024 earnings of $1.26 per share,
        beating estimates by 5%. Revenue came in at $85.8 billion,
        up 4.9% year-over-year. The company announced a $110 billion
        share buyback program.
        """
        
        entities = await recognizer.extract_entities(text)
        
        assert "AAPL" in entities["tickers"]
        assert any("Apple" in c for c in entities["companies"])
        assert "Q3 2024" in entities["dates"]
        assert any("$85.8 billion" in a for a in entities["amounts"])
        assert "4.9%" in entities["percentages"]
        assert "revenue" in entities["metrics"]
    
    @pytest.mark.asyncio
    async def test_news_credibility(self):
        """Test news source credibility scoring"""
        
        scorer = NewsCredibilityScorer()
        
        # Test tier 1 source
        tier1_result = await scorer.score_source("Bloomberg")
        assert tier1_result["tier"] == "tier1"
        assert tier1_result["credibility_score"] >= 0.8
        
        # Test tier 3 source
        tier3_result = await scorer.score_source("Reddit")
        assert tier3_result["tier"] == "tier3"
        assert tier3_result["credibility_score"] < 0.7
        
        # Test article scoring
        article = {
            "source": "Reuters",
            "published_at": datetime.utcnow().isoformat(),
            "title": "Tech stocks rally on strong earnings",
            "summary": "Major technology companies reported better than expected earnings, driving a 2% gain in the NASDAQ."
        }
        
        article_score = await scorer.score_article(article)
        assert article_score["overall_score"] > 0.7  # High quality article
        assert article_score["recommendation"] == "high_quality"
    
    @pytest.mark.asyncio
    async def test_financial_summarization(self):
        """Test financial text summarization"""
        
        summarizer = FinancialTextSummarizer()
        
        text = """
        Apple Inc. reported fiscal Q3 2024 earnings that exceeded Wall Street expectations.
        The company posted earnings per share of $1.26, beating the consensus estimate of $1.19.
        Revenue came in at $85.8 billion, up 4.9% year-over-year and above the expected $84.5 billion.
        iPhone revenue grew 3% to $39.3 billion, while Services revenue jumped 14% to $21.2 billion.
        The company announced a massive $110 billion share buyback program and raised its dividend by 4%.
        CEO Tim Cook cited strong demand in emerging markets and continued growth in the services segment.
        However, China revenue declined 6.5% due to increased competition and economic headwinds.
        Looking ahead, Apple provided Q4 guidance suggesting continued growth but at a slower pace.
        """
        
        result = await summarizer.summarize_financial_text(text, max_sentences=3)
        
        assert "summary" in result
        assert len(result["summary"]) > 0
        assert "key_points" in result
        assert len(result["key_points"]) > 0
        
        # Check that key metrics were extracted
        key_points = result["key_points"]
        assert any("$85.8 billion" in str(kp) for kp in key_points)


class TestRealtimeData:
    """Test real-time data capabilities"""
    
    def test_event_triggers(self):
        """Test event trigger conditions"""
        
        # Price movement trigger
        price_trigger = EventTrigger(
            MarketEvent.PRICE_UPDATE,
            lambda d: abs(d.get("change_percent", 0)) > 2.0,
            priority=7
        )
        
        # Should trigger on >2% move
        assert price_trigger.check({"change_percent": 2.5})
        assert price_trigger.check({"change_percent": -3.0})
        
        # Should not trigger on small moves
        assert not price_trigger.check({"change_percent": 1.5})
        assert not price_trigger.check({"change_percent": 0})
    
    @pytest.mark.asyncio
    async def test_market_aggregator(self):
        """Test market context aggregation"""
        
        aggregator = MarketDataAggregator()
        
        # Mock market data
        aggregator.market_indicators = {
            "vix": 25,
            "sp500_change": -1.5,
            "trend": "down"
        }
        
        context = await aggregator.update_market_context()
        
        assert "regime" in context
        assert context["regime"] in ["low_volatility", "normal", "elevated_volatility", "high_volatility"]
        assert "session" in context
        assert context["session"] in ["regular", "pre_market", "after_hours", "closed"]
    
    def test_event_driven_analyzer(self):
        """Test event-driven analysis system"""
        
        analyzer = EventDrivenAnalyzer()
        
        # Check default triggers are set up
        assert len(analyzer.triggers) > 0
        
        # Test adding custom trigger
        custom_trigger = EventTrigger(
            MarketEvent.TECHNICAL_SIGNAL,
            lambda d: d.get("signal") == "breakout",
            priority=8
        )
        
        analyzer.add_trigger(custom_trigger)
        assert custom_trigger in analyzer.triggers
        
        # Triggers should be sorted by priority
        priorities = [t.priority for t in analyzer.triggers]
        assert priorities == sorted(priorities, reverse=True)


class TestMultiTickerSupport:
    """Test multi-ticker analysis capabilities"""
    
    def test_comparative_analysis(self):
        """Test comparative analysis across multiple stocks"""
        
        reports = [
            {
                "ticker": "AAPL",
                "decision": {
                    "action": "Buy",
                    "rating": 4.2,
                    "expected_return_pct": 15.5,
                    "confidence": 0.85
                },
                "metadata": {"sector": "Technology"},
                "fundamentals": {"details": {"pe": 25.5, "roe": 0.35}},
                "growth_prospects": {"details": {"growth_outlook": {"overall_outlook": "Strong"}}},
                "valuation": {"details": {"consolidated_valuation": {"upside_downside_pct": 20}}}
            },
            {
                "ticker": "MSFT",
                "decision": {
                    "action": "Hold",
                    "rating": 3.5,
                    "expected_return_pct": 8.2,
                    "confidence": 0.75
                },
                "metadata": {"sector": "Technology"},
                "fundamentals": {"details": {"pe": 30.2, "roe": 0.28}},
                "growth_prospects": {"details": {"growth_outlook": {"overall_outlook": "Moderate"}}},
                "valuation": {"details": {"consolidated_valuation": {"upside_downside_pct": 10}}}
            },
            {
                "ticker": "GOOGL",
                "decision": {
                    "action": "Buy",
                    "rating": 4.0,
                    "expected_return_pct": 12.8,
                    "confidence": 0.80
                },
                "metadata": {"sector": "Technology"},
                "fundamentals": {"details": {"pe": 22.8, "roe": 0.30}},
                "growth_prospects": {"details": {"growth_outlook": {"overall_outlook": "Strong"}}},
                "valuation": {"details": {"consolidated_valuation": {"upside_downside_pct": 15}}}
            }
        ]
        
        comparative = create_comparative_analysis(reports)
        
        assert "rankings" in comparative
        assert len(comparative["rankings"]) == 3
        
        assert "recommendations" in comparative
        assert comparative["recommendations"]["best_overall"] == "AAPL"  # Highest rating
        assert comparative["recommendations"]["best_value"] == "GOOGL"  # Lowest P/E
        
        assert "portfolio_suggestion" in comparative
        suggestions = comparative["portfolio_suggestion"]
        if "suggested_allocation" in suggestions:
            # Should only include Buy recommendations
            assert "MSFT" not in suggestions["suggested_allocation"]  # Hold, not Buy
            assert "AAPL" in suggestions["suggested_allocation"]
            assert "GOOGL" in suggestions["suggested_allocation"]


class TestIntegration:
    """Integration tests for the enhanced system"""
    
    @pytest.mark.asyncio
    async def test_enhanced_score_calculation(self):
        """Test the enhanced scoring system end-to-end"""
        
        ticker = "AAPL"
        analysis = {
            "technicals": {"signals": {"score": 0.7}},
            "fundamentals": {
                "pe": 25,
                "roe": 0.30,
                "revenueGrowth": 0.15,
                "debtToEquity": 0.8
            },
            "growth_prospects": {
                "growth_outlook": {"overall_outlook": "Strong Growth Expected"}
            },
            "news_sentiment": {"score": 0.65},
            "youtube": {"score": 0.60},
            "valuation": {
                "consolidated_valuation": {"upside_downside_pct": 18}
            },
            "peer_analysis": {"relative_position": "Above-average performer"},
            "analyst_recommendations": {
                "consensus_analysis": {"implied_return": 22}
            }
        }
        
        confidences = {
            "technicals": 0.8,
            "fundamentals": 0.85,
            "growth_prospects": 0.75,
            "news_sentiment": 0.7,
            "youtube": 0.6,
            "valuation": 0.8,
            "peer_analysis": 0.75,
            "analyst_recommendations": 0.7
        }
        
        score, explanation = _calculate_enhanced_score(
            ticker, analysis, confidences, "Technology", "bull"
        )
        
        # Score should be positive given good metrics
        assert score > 0.5
        assert score <= 1.0
        
        # Explanation should have all components
        assert "total_score" in explanation
        assert "components" in explanation
        assert "contributions" in explanation
        
        # All major components should be present
        assert "technicals" in explanation["components"]
        assert "fundamentals" in explanation["components"]
        assert "growth_prospects" in explanation["components"]
        assert "sentiment" in explanation["components"]
        assert "valuation" in explanation["components"]


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
