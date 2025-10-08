"""
Enhanced NLP for financial domain using FinBERT and other specialized models
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import transformer models
# External transformer-based sentiment temporarily disabled
TRANSFORMERS_AVAILABLE = False


class FinancialSentimentAnalyzer:
    """
    Financial domain-specific sentiment analysis using FinBERT
    """
    
    def __init__(self, model_name: str | None = None):
        # No-op init while external model support is disabled
        self.model_name = model_name or ""
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.initialized = False
    
    def _initialize_model(self):
        # Disabled path
        self.initialized = False
    
    async def analyze_sentiment(
        self,
        texts: List[str],
        aggregate: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of financial texts
        
        Args:
            texts: List of text strings to analyze
            aggregate: Whether to aggregate results
            
        Returns:
            Sentiment analysis results
        """
        
        if not texts:
            return {"score": 0.5, "label": "neutral", "confidence": 0.0}
        
        # Fallback only (external model disabled)
        return await self._fallback_sentiment(texts, aggregate)
        
        try:
            # Run sentiment analysis in thread pool to avoid blocking
            results = await asyncio.to_thread(self._analyze_batch, texts)
            
            if aggregate:
                return self._aggregate_sentiments(results)
            else:
                return {"individual_sentiments": results}
                
        except Exception as e:
            logger.error(f"FinBERT analysis failed: {e}")
            return await self._fallback_sentiment(texts, aggregate)
    
    def _analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analyze a batch of texts"""
        
        # Truncate texts to model max length (usually 512 tokens)
        max_length = 512
        truncated_texts = []
        for text in texts:
            if len(text) > max_length * 4:  # Rough char to token ratio
                truncated_texts.append(text[:max_length * 4])
            else:
                truncated_texts.append(text)
        
        # Get predictions
        predictions = self.pipeline(truncated_texts)
        
        # Convert to standardized format
        results = []
        for pred in predictions:
            label = pred["label"].lower()
            score = pred["score"]
            
            # Map FinBERT labels to normalized sentiment
            if label == "positive":
                sentiment_score = 0.5 + (score * 0.5)  # 0.5 to 1.0
            elif label == "negative":
                sentiment_score = 0.5 - (score * 0.5)  # 0.0 to 0.5
            else:  # neutral
                sentiment_score = 0.5
            
            results.append({
                "label": label,
                "score": sentiment_score,
                "confidence": score
            })
        
        return results
    
    def _aggregate_sentiments(self, sentiments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple sentiment scores"""
        
        if not sentiments:
            return {"score": 0.5, "label": "neutral", "confidence": 0.0}
        
        # Calculate weighted average based on confidence
        total_weight = 0
        weighted_sum = 0
        label_counts = {"positive": 0, "negative": 0, "neutral": 0}
        
        for sent in sentiments:
            weight = sent["confidence"]
            weighted_sum += sent["score"] * weight
            total_weight += weight
            label_counts[sent["label"]] += 1
        
        avg_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        # Determine overall label
        if avg_score > 0.6:
            overall_label = "positive"
        elif avg_score < 0.4:
            overall_label = "negative"
        else:
            overall_label = "neutral"
        
        # Calculate confidence as average of individual confidences
        avg_confidence = sum(s["confidence"] for s in sentiments) / len(sentiments)
        
        return {
            "score": avg_score,
            "label": overall_label,
            "confidence": avg_confidence,
            "distribution": label_counts,
            "sample_size": len(sentiments)
        }
    
    async def _fallback_sentiment(
        self,
        texts: List[str],
        aggregate: bool
    ) -> Dict[str, Any]:
        """Fallback sentiment analysis using keyword matching"""
        
        positive_words = {
            "gain", "profit", "growth", "increase", "rise", "improve", "strong",
            "outperform", "beat", "exceed", "upgrade", "buy", "bullish", "surge",
            "rally", "breakout", "momentum", "record", "high", "positive"
        }
        
        negative_words = {
            "loss", "decline", "fall", "decrease", "drop", "weak", "underperform",
            "miss", "downgrade", "sell", "bearish", "crash", "correction", "low",
            "negative", "concern", "risk", "warning", "cut", "reduce"
        }
        
        results = []
        
        for text in texts:
            text_lower = text.lower()
            words = set(re.findall(r'\b\w+\b', text_lower))
            
            pos_count = len(words & positive_words)
            neg_count = len(words & negative_words)
            total = pos_count + neg_count
            
            if total > 0:
                score = 0.5 + ((pos_count - neg_count) / (total * 2))
                score = max(0.0, min(1.0, score))
            else:
                score = 0.5
            
            if score > 0.6:
                label = "positive"
            elif score < 0.4:
                label = "negative"
            else:
                label = "neutral"
            
            results.append({
                "label": label,
                "score": score,
                "confidence": min(0.7, total / 10)  # Simple confidence based on keyword count
            })
        
        if aggregate:
            return self._aggregate_sentiments(results)
        else:
            return {"individual_sentiments": results}


class EntityRecognizer:
    """
    Extract and disambiguate financial entities from text
    """
    
    def __init__(self):
        self.company_patterns = [
            r'\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Inc|Corp|Ltd|LLC|Company|Co)\b',
            r'\b[A-Z]{2,5}\b(?=\s+(?:stock|shares|price))',  # Ticker symbols
        ]
        
        self.financial_metrics = {
            "revenue", "earnings", "profit", "loss", "margin", "ebitda",
            "eps", "pe", "ratio", "dividend", "yield", "growth", "debt"
        }
        
        self.temporal_patterns = [
            r'\b(?:Q[1-4]\s+\d{4})\b',  # Q1 2024
            r'\b(?:FY\s*\d{4})\b',  # FY2024
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b',
        ]
    
    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract financial entities from text"""
        
        entities = {
            "companies": [],
            "tickers": [],
            "metrics": [],
            "dates": [],
            "amounts": []
        }
        
        # Extract companies and tickers
        for pattern in self.company_patterns:
            matches = re.findall(pattern, text)
            entities["companies"].extend(matches)
        
        # Extract ticker symbols (uppercase 2-5 letter words)
        tickers = re.findall(r'\b[A-Z]{2,5}\b', text)
        # Filter to likely tickers (you could validate against a ticker list)
        entities["tickers"] = [t for t in tickers if len(t) <= 5]
        
        # Extract financial metrics
        text_lower = text.lower()
        for metric in self.financial_metrics:
            if metric in text_lower:
                entities["metrics"].append(metric)
        
        # Extract dates
        for pattern in self.temporal_patterns:
            matches = re.findall(pattern, text)
            entities["dates"].extend(matches)
        
        # Extract monetary amounts
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:billion|million|thousand|B|M|K))?'
        amounts = re.findall(amount_pattern, text)
        entities["amounts"] = amounts
        
        # Extract percentages
        percent_pattern = r'[-+]?\d+(?:\.\d+)?%'
        percentages = re.findall(percent_pattern, text)
        entities["percentages"] = percentages
        
        return entities
    
    async def disambiguate_ticker(
        self,
        ticker: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Disambiguate a ticker symbol using context
        """
        
        # Look for exchange indicators
        exchanges = {
            "NYSE": ["NYSE", "New York Stock Exchange"],
            "NASDAQ": ["NASDAQ", "Nasdaq"],
            "LSE": ["LSE", "London Stock Exchange"],
            "TSE": ["TSE", "Tokyo Stock Exchange"],
            "NSE": ["NSE", "National Stock Exchange", "India"]
        }
        
        detected_exchange = None
        for exchange, keywords in exchanges.items():
            for keyword in keywords:
                if keyword.lower() in context.lower():
                    detected_exchange = exchange
                    break
        
        # Look for company name mentions
        company_indicators = re.findall(
            rf'{ticker}\s+\(([^)]+)\)',  # AAPL (Apple Inc.)
            context
        )
        
        company_name = company_indicators[0] if company_indicators else None
        
        # Look for sector/industry context
        sectors = ["technology", "finance", "healthcare", "energy", "consumer", "industrial"]
        detected_sector = None
        for sector in sectors:
            if sector in context.lower():
                detected_sector = sector
                break
        
        return {
            "ticker": ticker,
            "exchange": detected_exchange,
            "company_name": company_name,
            "sector": detected_sector,
            "confidence": 0.8 if (detected_exchange or company_name) else 0.5
        }


class NewsCredibilityScorer:
    """
    Score the credibility and relevance of news sources
    """
    
    # Tier 1: Most credible financial sources
    TIER1_SOURCES = {
        "reuters", "bloomberg", "wall street journal", "financial times",
        "barrons", "cnbc", "marketwatch", "yahoo finance", "seeking alpha"
    }
    
    # Tier 2: Credible but potentially biased
    TIER2_SOURCES = {
        "motley fool", "investorplace", "benzinga", "thestreet",
        "business insider", "forbes", "fortune", "economist"
    }
    
    # Tier 3: User-generated or less reliable
    TIER3_SOURCES = {
        "reddit", "twitter", "stocktwits", "blog", "medium",
        "youtube", "tiktok", "facebook"
    }
    
    def __init__(self):
        self.source_scores = {
            "tier1": 0.9,
            "tier2": 0.7,
            "tier3": 0.5,
            "unknown": 0.6
        }
    
    async def score_source(self, source: str) -> Dict[str, Any]:
        """Score a news source for credibility"""
        
        source_lower = source.lower()
        
        # Determine tier
        tier = "unknown"
        if any(t1 in source_lower for t1 in self.TIER1_SOURCES):
            tier = "tier1"
        elif any(t2 in source_lower for t2 in self.TIER2_SOURCES):
            tier = "tier2"
        elif any(t3 in source_lower for t3 in self.TIER3_SOURCES):
            tier = "tier3"
        
        credibility_score = self.source_scores[tier]
        
        return {
            "source": source,
            "tier": tier,
            "credibility_score": credibility_score,
            "is_professional": tier in ["tier1", "tier2"],
            "is_user_generated": tier == "tier3"
        }
    
    async def score_article(
        self,
        article: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Score an article based on multiple factors"""
        
        scores = {}
        
        # Source credibility
        source = article.get("source", "unknown")
        source_score = await self.score_source(source)
        scores["source_credibility"] = source_score["credibility_score"]
        
        # Recency (newer is better)
        published_date = article.get("published_at")
        if published_date:
            try:
                pub_dt = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                age_hours = (datetime.utcnow() - pub_dt.replace(tzinfo=None)).total_seconds() / 3600
                
                if age_hours < 1:
                    scores["recency"] = 1.0
                elif age_hours < 24:
                    scores["recency"] = 0.9
                elif age_hours < 72:
                    scores["recency"] = 0.7
                elif age_hours < 168:  # 1 week
                    scores["recency"] = 0.5
                else:
                    scores["recency"] = 0.3
            except:
                scores["recency"] = 0.5
        else:
            scores["recency"] = 0.5
        
        # Content quality indicators
        content = article.get("summary", "") + " " + article.get("title", "")
        
        # Check for clickbait indicators
        clickbait_phrases = [
            "you won't believe", "shocking", "destroys", "slams",
            "one weird trick", "doctors hate", "breaking:", "urgent:"
        ]
        has_clickbait = any(phrase in content.lower() for phrase in clickbait_phrases)
        scores["content_quality"] = 0.5 if has_clickbait else 0.8
        
        # Check for financial data presence
        has_numbers = bool(re.search(r'\d+\.?\d*[%$]', content))
        has_metrics = any(metric in content.lower() for metric in ["revenue", "earnings", "profit", "growth"])
        scores["data_richness"] = 0.8 if (has_numbers and has_metrics) else 0.5
        
        # Calculate overall score
        weights = {
            "source_credibility": 0.4,
            "recency": 0.2,
            "content_quality": 0.2,
            "data_richness": 0.2
        }
        
        overall_score = sum(scores[k] * weights[k] for k in weights)
        
        return {
            "article_id": article.get("url", "unknown"),
            "scores": scores,
            "overall_score": overall_score,
            "tier": source_score["tier"],
            "recommendation": "high_quality" if overall_score > 0.7 else "moderate" if overall_score > 0.5 else "low_quality"
        }


class FinancialTextSummarizer:
    """
    Specialized summarization for financial texts
    """
    
    def __init__(self):
        self.key_info_patterns = [
            r'(?:revenue|sales).*?(?:\$[\d,]+(?:\.\d+)?[BMK]?|\d+%)',
            r'(?:earnings|profit|income).*?(?:\$[\d,]+(?:\.\d+)?[BMK]?|\d+%)',
            r'(?:guidance|forecast|outlook).*?(?:\$[\d,]+(?:\.\d+)?[BMK]?|\d+%)',
            r'(?:beat|miss|exceeded|fell short).*?(?:expectations|estimates)',
            r'(?:upgrade|downgrade|maintain|initiate).*?(?:buy|sell|hold|neutral)',
        ]
    
    async def summarize_financial_text(
        self,
        text: str,
        max_sentences: int = 3
    ) -> Dict[str, Any]:
        """
        Extract key financial information and create summary
        """
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return {"summary": "", "key_points": []}
        
        # Score sentences based on financial relevance
        scored_sentences = []
        
        for sentence in sentences:
            score = 0
            
            # Check for key financial patterns
            for pattern in self.key_info_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    score += 2
            
            # Check for financial metrics
            if re.search(r'\$[\d,]+', sentence):
                score += 1
            if re.search(r'\d+\.?\d*%', sentence):
                score += 1
            
            # Check for important keywords
            important_words = ["revenue", "earnings", "profit", "growth", "guidance", "forecast"]
            for word in important_words:
                if word in sentence.lower():
                    score += 1
            
            # Length penalty (prefer concise sentences)
            if len(sentence) > 200:
                score -= 1
            
            scored_sentences.append((sentence, score))
        
        # Sort by score and select top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = scored_sentences[:max_sentences]
        
        # Reorder by original position for coherence
        original_order = []
        for sent, score in top_sentences:
            try:
                idx = sentences.index(sent)
                original_order.append((idx, sent))
            except ValueError:
                continue
        
        original_order.sort(key=lambda x: x[0])
        summary_sentences = [sent for _, sent in original_order]
        
        # Extract key points
        key_points = []
        for sentence, score in scored_sentences[:5]:  # Top 5 sentences
            # Extract specific metrics
            amounts = re.findall(r'\$[\d,]+(?:\.\d+)?[BMK]?', sentence)
            percentages = re.findall(r'\d+\.?\d*%', sentence)
            
            if amounts or percentages:
                key_points.append({
                    "text": sentence[:100] + "..." if len(sentence) > 100 else sentence,
                    "metrics": {
                        "amounts": amounts,
                        "percentages": percentages
                    }
                })
        
        return {
            "summary": " ".join(summary_sentences),
            "key_points": key_points[:3],  # Top 3 key points
            "sentence_count": len(sentences),
            "summary_sentences": len(summary_sentences)
        }
