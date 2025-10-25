"""
Horizon Filtering Engine
Phase 1: Core Investment Framework - Time Horizon Analysis
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class AnalysisHorizon(str, Enum):
    """Analysis time horizons"""
    SHORT_TERM = "short_term"  # 0-6 months
    MEDIUM_TERM = "medium_term"  # 6-18 months  
    LONG_TERM = "long_term"  # 18+ months


class HorizonFilteringEngine:
    """
    Engine for filtering and adjusting analysis based on time horizons
    """
    
    def __init__(self):
        self.horizon_configs = {
            AnalysisHorizon.SHORT_TERM: {
                "days_range": (0, 180),
                "weight_technicals": 0.4,
                "weight_sentiment": 0.3,
                "weight_fundamentals": 0.2,
                "weight_growth": 0.1,
                "volatility_adjustment": 1.2,
                "confidence_discount": 0.9
            },
            AnalysisHorizon.MEDIUM_TERM: {
                "days_range": (180, 540),
                "weight_technicals": 0.25,
                "weight_sentiment": 0.2,
                "weight_fundamentals": 0.35,
                "weight_growth": 0.2,
                "volatility_adjustment": 1.0,
                "confidence_discount": 1.0
            },
            AnalysisHorizon.LONG_TERM: {
                "days_range": (540, 1095),
                "weight_technicals": 0.1,
                "weight_sentiment": 0.1,
                "weight_fundamentals": 0.4,
                "weight_growth": 0.4,
                "volatility_adjustment": 0.8,
                "confidence_discount": 1.1
            }
        }
    
    def determine_horizons(self, short_term_days: int, long_term_days: int) -> Tuple[AnalysisHorizon, AnalysisHorizon]:
        """
        Determine analysis horizons based on user input
        
        Args:
            short_term_days: Short-term horizon in days
            long_term_days: Long-term horizon in days
            
        Returns:
            Tuple of (short_horizon, long_horizon)
        """
        short_horizon = self._classify_horizon(short_term_days)
        long_horizon = self._classify_horizon(long_term_days)
        
        logger.info(f"Determined horizons: Short={short_horizon.value}, Long={long_horizon.value}")
        return short_horizon, long_horizon
    
    def _classify_horizon(self, days: int) -> AnalysisHorizon:
        """Classify days into horizon category"""
        if days <= 180:
            return AnalysisHorizon.SHORT_TERM
        elif days <= 540:
            return AnalysisHorizon.MEDIUM_TERM
        else:
            return AnalysisHorizon.LONG_TERM
    
    def apply_horizon_filtering(
        self,
        analysis_data: Dict[str, Any],
        horizon: AnalysisHorizon,
        confidences: Dict[str, float]
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """
        Apply horizon-specific filtering to analysis data
        
        Args:
            analysis_data: Raw analysis data from all nodes
            horizon: Target analysis horizon
            confidences: Section confidence scores
            
        Returns:
            Tuple of (filtered_analysis_data, adjusted_confidences)
        """
        config = self.horizon_configs[horizon]
        
        # Create filtered analysis data
        filtered_data = analysis_data.copy()
        
        # Adjust section weights based on horizon
        filtered_data = self._adjust_section_weights(filtered_data, config)
        
        # Apply horizon-specific adjustments
        filtered_data = self._apply_horizon_adjustments(filtered_data, horizon, config)
        
        # Adjust confidences based on horizon
        adjusted_confidences = self._adjust_confidences(confidences, config)
        
        # Add horizon metadata
        filtered_data["horizon_metadata"] = {
            "horizon": horizon.value,
            "config": config,
            "applied_at": datetime.now().isoformat()
        }
        
        logger.info(f"Applied {horizon.value} filtering to analysis data")
        return filtered_data, adjusted_confidences
    
    def _adjust_section_weights(self, analysis_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Adjust section weights based on horizon importance"""
        filtered_data = analysis_data.copy()
        
        # Add horizon-specific weights to each section
        section_weights = {
            "technicals": config["weight_technicals"],
            "news_sentiment": config["weight_sentiment"],
            "fundamentals": config["weight_fundamentals"],
            "growth_prospects": config["weight_growth"]
        }
        
        filtered_data["horizon_weights"] = section_weights
        
        # Adjust technical analysis for short-term focus
        if config["weight_technicals"] > 0.3:  # Short-term
            technicals = filtered_data.get("technicals", {}).get("details", {})
            if technicals:
                # Emphasize short-term technical indicators
                technicals["horizon_focus"] = "short_term_indicators"
                technicals["priority_indicators"] = ["RSI", "MACD", "Bollinger_Bands"]
        
        # Adjust fundamentals for long-term focus
        if config["weight_fundamentals"] > 0.35:  # Long-term
            fundamentals = filtered_data.get("fundamentals", {}).get("details", {})
            if fundamentals:
                # Emphasize long-term fundamental metrics
                fundamentals["horizon_focus"] = "long_term_fundamentals"
                fundamentals["priority_metrics"] = ["ROE", "ROIC", "Debt_to_Equity", "FCF_Growth"]
        
        return filtered_data
    
    def _apply_horizon_adjustments(self, analysis_data: Dict[str, Any], horizon: AnalysisHorizon, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply horizon-specific adjustments to analysis"""
        filtered_data = analysis_data.copy()
        
        # Adjust volatility expectations
        volatility_adjustment = config["volatility_adjustment"]
        
        # Adjust technical analysis
        technicals = filtered_data.get("technicals", {}).get("details", {})
        if technicals:
            # Adjust RSI thresholds based on horizon
            if "rsi" in technicals:
                if horizon == AnalysisHorizon.SHORT_TERM:
                    # More sensitive to overbought/oversold in short-term
                    technicals["rsi_adjusted_thresholds"] = {"overbought": 70, "oversold": 30}
                else:
                    # Less sensitive in long-term
                    technicals["rsi_adjusted_thresholds"] = {"overbought": 75, "oversold": 25}
        
        # Adjust sentiment analysis
        sentiment_sections = ["news_sentiment", "youtube_sentiment"]
        for section in sentiment_sections:
            sentiment_data = filtered_data.get(section, {}).get("details", {})
            if sentiment_data:
                # Short-term sentiment is more volatile
                if horizon == AnalysisHorizon.SHORT_TERM:
                    sentiment_data["volatility_factor"] = volatility_adjustment
                    sentiment_data["horizon_note"] = "Short-term sentiment analysis with higher volatility expectations"
                else:
                    sentiment_data["volatility_factor"] = 1.0 / volatility_adjustment
                    sentiment_data["horizon_note"] = "Long-term sentiment analysis with trend focus"
        
        # Adjust growth prospects
        growth_data = filtered_data.get("growth_prospects", {}).get("details", {})
        if growth_data:
            if horizon == AnalysisHorizon.SHORT_TERM:
                growth_data["focus"] = "near_term_catalysts"
                growth_data["timeframe"] = "0-6 months"
            else:
                growth_data["focus"] = "sustainable_growth"
                growth_data["timeframe"] = "18+ months"
        
        # Adjust valuation analysis
        valuation_data = filtered_data.get("valuation", {}).get("details", {})
        if valuation_data:
            if horizon == AnalysisHorizon.SHORT_TERM:
                valuation_data["focus"] = "relative_valuation"
                valuation_data["priority_methods"] = ["P/E", "P/B", "EV/EBITDA"]
            else:
                valuation_data["focus"] = "intrinsic_valuation"
                valuation_data["priority_methods"] = ["DCF", "DDM", "Sum_of_Parts"]
        
        return filtered_data
    
    def _adjust_confidences(self, confidences: Dict[str, float], config: Dict[str, Any]) -> Dict[str, float]:
        """Adjust confidence scores based on horizon"""
        adjusted_confidences = {}
        confidence_discount = config["confidence_discount"]
        
        for section, confidence in confidences.items():
            # Apply horizon-specific confidence adjustments
            if section in ["technicals", "news_sentiment"] and config["weight_technicals"] > 0.3:
                # Higher confidence for technicals in short-term
                adjusted_confidences[section] = min(1.0, confidence * confidence_discount)
            elif section in ["fundamentals", "growth_prospects"] and config["weight_fundamentals"] > 0.35:
                # Higher confidence for fundamentals in long-term
                adjusted_confidences[section] = min(1.0, confidence * confidence_discount)
            else:
                # Standard adjustment
                adjusted_confidences[section] = confidence * confidence_discount
        
        return adjusted_confidences
    
    def calculate_horizon_weighted_score(
        self,
        section_scores: Dict[str, float],
        confidences: Dict[str, float],
        horizon: AnalysisHorizon
    ) -> float:
        """
        Calculate horizon-weighted composite score
        
        Args:
            section_scores: Individual section scores
            confidences: Section confidence scores
            horizon: Analysis horizon
            
        Returns:
            Horizon-weighted composite score
        """
        config = self.horizon_configs[horizon]
        
        weighted_score = 0.0
        total_weight = 0.0
        
        # Apply horizon-specific weights
        weights = {
            "technicals": config["weight_technicals"],
            "news_sentiment": config["weight_sentiment"],
            "fundamentals": config["weight_fundamentals"],
            "growth_prospects": config["weight_growth"],
            "valuation": 0.15,  # Always important
            "peer_analysis": 0.1,  # Always important
            "sector_macro": 0.1,  # Always important
            "leadership": 0.05,  # Always important
            "cashflow": 0.05,  # Always important
            "analyst_recommendations": 0.05  # Always important
        }
        
        for section, score in section_scores.items():
            weight = weights.get(section, 0.05)
            confidence = confidences.get(section, 0.5)
            
            # Weight by both horizon importance and confidence
            effective_weight = weight * confidence
            weighted_score += score * effective_weight
            total_weight += effective_weight
        
        return weighted_score / total_weight if total_weight > 0 else 0.5
    
    def generate_horizon_summary(
        self,
        horizon: AnalysisHorizon,
        analysis_data: Dict[str, Any],
        composite_score: float
    ) -> Dict[str, Any]:
        """
        Generate horizon-specific summary
        
        Args:
            horizon: Analysis horizon
            analysis_data: Filtered analysis data
            confidences: Adjusted confidence scores
            
        Returns:
            Horizon-specific summary
        """
        config = self.horizon_configs[horizon]
        
        summary = {
            "horizon": horizon.value,
            "days_range": config["days_range"],
            "focus_areas": [],
            "key_considerations": [],
            "confidence_level": "moderate"
        }
        
        # Determine focus areas based on weights
        if config["weight_technicals"] > 0.3:
            summary["focus_areas"].append("Technical momentum and chart patterns")
        if config["weight_sentiment"] > 0.2:
            summary["focus_areas"].append("Market sentiment and news flow")
        if config["weight_fundamentals"] > 0.35:
            summary["focus_areas"].append("Fundamental business metrics")
        if config["weight_growth"] > 0.3:
            summary["focus_areas"].append("Growth prospects and catalysts")
        
        # Add key considerations
        if horizon == AnalysisHorizon.SHORT_TERM:
            summary["key_considerations"] = [
                "Higher volatility expected",
                "Technical indicators more relevant",
                "Earnings and guidance critical",
                "Market sentiment impact significant"
            ]
        elif horizon == AnalysisHorizon.LONG_TERM:
            summary["key_considerations"] = [
                "Fundamental business quality paramount",
                "Competitive positioning crucial",
                "Management execution important",
                "Industry trends and disruption risks"
            ]
        else:  # Medium-term
            summary["key_considerations"] = [
                "Balanced approach required",
                "Both technical and fundamental factors",
                "Catalyst timing important",
                "Risk management essential"
            ]
        
        # Determine confidence level
        if composite_score >= 0.7:
            summary["confidence_level"] = "high"
        elif composite_score >= 0.5:
            summary["confidence_level"] = "moderate"
        else:
            summary["confidence_level"] = "low"
        
        return summary
    
    def get_horizon_recommendations(
        self,
        short_term_score: float,
        long_term_score: float,
        short_horizon: AnalysisHorizon,
        long_horizon: AnalysisHorizon
    ) -> Dict[str, Any]:
        """
        Get horizon-specific recommendations
        
        Args:
            short_term_score: Short-term composite score
            long_term_score: Long-term composite score
            short_horizon: Short-term horizon type
            long_horizon: Long-term horizon type
            
        Returns:
            Horizon-specific recommendations
        """
        recommendations = {
            "short_term": {
                "score": short_term_score,
                "horizon": short_horizon.value,
                "recommendation": self._score_to_recommendation(short_term_score),
                "confidence": self._score_to_confidence(short_term_score),
                "key_factors": self._get_horizon_factors(short_horizon)
            },
            "long_term": {
                "score": long_term_score,
                "horizon": long_horizon.value,
                "recommendation": self._score_to_recommendation(long_term_score),
                "confidence": self._score_to_confidence(long_term_score),
                "key_factors": self._get_horizon_factors(long_horizon)
            }
        }
        
        # Add comparative analysis
        score_diff = long_term_score - short_term_score
        if abs(score_diff) > 0.1:
            if score_diff > 0:
                recommendations["comparative_analysis"] = "Long-term outlook more favorable than short-term"
            else:
                recommendations["comparative_analysis"] = "Short-term outlook more favorable than long-term"
        else:
            recommendations["comparative_analysis"] = "Consistent outlook across time horizons"
        
        return recommendations
    
    def _score_to_recommendation(self, score: float) -> str:
        """Convert score to recommendation"""
        if score >= 0.8:
            return "Strong Buy"
        elif score >= 0.6:
            return "Buy"
        elif score >= 0.4:
            return "Hold"
        elif score >= 0.2:
            return "Sell"
        else:
            return "Strong Sell"
    
    def _score_to_confidence(self, score: float) -> str:
        """Convert score to confidence level"""
        if score >= 0.7:
            return "High"
        elif score >= 0.5:
            return "Moderate"
        else:
            return "Low"
    
    def _get_horizon_factors(self, horizon: AnalysisHorizon) -> List[str]:
        """Get key factors for horizon"""
        if horizon == AnalysisHorizon.SHORT_TERM:
            return ["Technical momentum", "Earnings expectations", "Market sentiment", "Volatility"]
        elif horizon == AnalysisHorizon.LONG_TERM:
            return ["Business fundamentals", "Competitive moats", "Growth prospects", "Management quality"]
        else:  # Medium-term
            return ["Catalyst timing", "Valuation", "Sector trends", "Risk management"]


# Global instance
horizon_engine = HorizonFilteringEngine()
