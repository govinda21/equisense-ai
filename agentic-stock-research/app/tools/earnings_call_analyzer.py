"""
Earnings Call & Transcript Analysis System

Implements comprehensive earnings call analysis to extract management sentiment,
guidance, and key insights from quarterly earnings calls.

Features:
- Multi-source transcript integration
- Sentiment analysis and tone detection
- Guidance extraction and tracking
- Q&A session analysis
- Management defensiveness scoring
- Key topic extraction and visualization
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

import aiohttp
from bs4 import BeautifulSoup
# Optional imports for NLP processing
try:
    import nltk
    from textblob import TextBlob
    NLP_PROCESSING_AVAILABLE = True
except ImportError:
    NLP_PROCESSING_AVAILABLE = False
    logger.warning("NLP processing libraries not available. Advanced sentiment analysis will be disabled.")

import yfinance as yf

from app.cache.redis_cache import get_cache_manager
from app.tools.llm_orchestrator import get_llm_orchestrator, TaskType, TaskComplexity

logger = logging.getLogger(__name__)

# Download required NLTK data (only if available)
if NLP_PROCESSING_AVAILABLE:
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')


class CallType(Enum):
    """Types of earnings calls"""
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    CONFERENCE = "conference"
    INVESTOR_DAY = "investor_day"


@dataclass
class EarningsCall:
    """Earnings call data structure"""
    ticker: str
    call_date: datetime
    call_type: CallType
    quarter: str  # e.g., "Q1 2024"
    fiscal_year: int
    transcript_url: str
    audio_url: Optional[str] = None
    transcript_text: Optional[str] = None
    participants: List[str] = field(default_factory=list)
    duration_minutes: Optional[int] = None
    call_id: Optional[str] = None


@dataclass
class CallAnalysis:
    """Earnings call analysis results"""
    ticker: str
    call_date: datetime
    quarter: str
    
    # Sentiment Analysis
    overall_sentiment: float  # -1 to 1
    management_tone: str  # "bullish", "cautious", "defensive", "optimistic"
    confidence_score: float  # 0 to 1
    
    # Guidance Analysis
    revenue_guidance: Optional[Dict[str, Any]] = None
    earnings_guidance: Optional[Dict[str, Any]] = None
    margin_guidance: Optional[Dict[str, Any]] = None
    capex_guidance: Optional[Dict[str, Any]] = None
    
    # Q&A Analysis
    analyst_questions: List[str] = field(default_factory=list)
    management_responses: List[str] = field(default_factory=list)
    defensiveness_score: float = 0.0  # 0 to 1
    topics_avoided: List[str] = field(default_factory=list)
    
    # Key Topics
    key_topics: List[str] = field(default_factory=list)
    concerns_raised: List[str] = field(default_factory=list)
    new_initiatives: List[str] = field(default_factory=list)
    
    # Performance Metrics
    call_quality_score: float = 0.0  # 0 to 1
    information_density: float = 0.0  # 0 to 1
    transparency_score: float = 0.0  # 0 to 1
    
    # Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    data_sources: List[str] = field(default_factory=list)


class TranscriptSource:
    """Abstract base class for transcript sources"""
    
    @abstractmethod
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get earnings call transcripts for a ticker"""
        pass
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Get source name"""
        pass


class SeekingAlphaSource(TranscriptSource):
    """Seeking Alpha transcript source"""
    
    def __init__(self):
        self.base_url = "https://seekingalpha.com"
        self.cache = get_cache_manager()
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )
        return self.session
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get Seeking Alpha transcripts"""
        cache_key = f"seeking_alpha_transcripts:{ticker}:{days_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved Seeking Alpha transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        try:
            session = await self._get_session()
            
            # Search for earnings calls
            search_url = f"{self.base_url}/symbol/{ticker}/earnings/transcripts"
            
            # Rate limiting
            await asyncio.sleep(1.0)
            
            async with session.get(search_url) as response:
                if response.status != 200:
                    logger.warning(f"Seeking Alpha returned {response.status} for {ticker}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract transcript links
                transcripts = []
                transcript_links = soup.find_all('a', href=re.compile(r'/article/\d+.*transcript'))
                
                for link in transcript_links[:10]:  # Limit to recent 10
                    try:
                        transcript_url = f"{self.base_url}{link['href']}"
                        title = link.get_text(strip=True)
                        
                        # Extract date from title or URL
                        call_date = self._extract_date_from_title(title)
                        
                        if call_date and (datetime.now() - call_date).days <= days_back:
                            earnings_call = EarningsCall(
                                ticker=ticker,
                                call_date=call_date,
                                call_type=CallType.EARNINGS,
                                quarter=self._extract_quarter_from_title(title),
                                fiscal_year=call_date.year,
                                transcript_url=transcript_url,
                                participants=[],
                                call_id=link['href'].split('/')[-1]
                            )
                            transcripts.append(earnings_call)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing Seeking Alpha transcript link: {e}")
                        continue
                
                # Cache results for 4 hours
                await self.cache.set(cache_key, [call.__dict__ for call in transcripts], ttl=14400)
                
                logger.info(f"Retrieved {len(transcripts)} Seeking Alpha transcripts for {ticker}")
                return transcripts
        
        except Exception as e:
            logger.error(f"Error fetching Seeking Alpha transcripts for {ticker}: {e}")
            return []
    
    def _extract_date_from_title(self, title: str) -> Optional[datetime]:
        """Extract date from transcript title"""
        try:
            # Common patterns: "Q1 2024 Earnings Call Transcript", "2024-01-15 Earnings Call"
            patterns = [
                r'(\w+)\s+(\d{4})',  # Q1 2024
                r'(\d{4})-(\d{2})-(\d{2})',  # 2024-01-15
                r'(\w+)\s+(\d{1,2}),\s+(\d{4})',  # January 15, 2024
            ]
            
            for pattern in patterns:
                match = re.search(pattern, title)
                if match:
                    if len(match.groups()) == 2:  # Q1 2024
                        quarter, year = match.groups()
                        # Convert quarter to approximate date
                        quarter_num = {'Q1': 1, 'Q2': 4, 'Q3': 7, 'Q4': 10}.get(quarter.upper(), 1)
                        return datetime(int(year), quarter_num, 15)
                    elif len(match.groups()) == 3:
                        if '-' in title:  # 2024-01-15
                            year, month, day = match.groups()
                            return datetime(int(year), int(month), int(day))
                        else:  # January 15, 2024
                            month_name, day, year = match.groups()
                            month = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }.get(month_name.lower(), 1)
                            return datetime(int(year), month, int(day))
            
            return None
            
        except Exception:
            return None
    
    def _extract_quarter_from_title(self, title: str) -> str:
        """Extract quarter from title"""
        match = re.search(r'(Q[1-4])\s+(\d{4})', title, re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()} {match.group(2)}"
        return "Unknown"
    
    def get_source_name(self) -> str:
        return "Seeking Alpha"


class AlphaStreetSource(TranscriptSource):
    """Alpha Street transcript source (premium)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.alphastreet.com/v1"
        self.cache = get_cache_manager()
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            headers = {'User-Agent': 'EquiSense AI/1.0'}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers=headers
            )
        return self.session
    
    async def get_transcripts(self, ticker: str, days_back: int = 90) -> List[EarningsCall]:
        """Get Alpha Street transcripts"""
        if not self.api_key:
            logger.warning("Alpha Street API key not provided")
            return []
        
        cache_key = f"alpha_street_transcripts:{ticker}:{days_back}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved Alpha Street transcripts from cache for {ticker}")
            return [EarningsCall(**call) for call in cached_result]
        
        try:
            session = await self._get_session()
            
            # Get earnings calls
            url = f"{self.base_url}/earnings-calls"
            params = {
                'symbol': ticker,
                'limit': 10,
                'days_back': days_back
            }
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(f"Alpha Street returned {response.status} for {ticker}")
                    return []
                
                data = await response.json()
                transcripts = []
                
                for call_data in data.get('calls', []):
                    try:
                        call_date = datetime.fromisoformat(call_data['date'].replace('Z', '+00:00'))
                        
                        earnings_call = EarningsCall(
                            ticker=ticker,
                            call_date=call_date,
                            call_type=CallType.EARNINGS,
                            quarter=call_data.get('quarter', 'Unknown'),
                            fiscal_year=call_date.year,
                            transcript_url=call_data.get('transcript_url', ''),
                            audio_url=call_data.get('audio_url'),
                            transcript_text=call_data.get('transcript'),
                            participants=call_data.get('participants', []),
                            duration_minutes=call_data.get('duration_minutes'),
                            call_id=call_data.get('id')
                        )
                        transcripts.append(earnings_call)
                    
                    except Exception as e:
                        logger.warning(f"Error parsing Alpha Street call data: {e}")
                        continue
                
                # Cache results for 4 hours
                await self.cache.set(cache_key, [call.__dict__ for call in transcripts], ttl=14400)
                
                logger.info(f"Retrieved {len(transcripts)} Alpha Street transcripts for {ticker}")
                return transcripts
        
        except Exception as e:
            logger.error(f"Error fetching Alpha Street transcripts for {ticker}: {e}")
            return []
    
    def get_source_name(self) -> str:
        return "Alpha Street"


class EarningsCallAnalyzer:
    """Main earnings call analysis system"""
    
    def __init__(self):
        self.sources = [
            SeekingAlphaSource(),
            AlphaStreetSource()  # Will be empty if no API key
        ]
        self.cache = get_cache_manager()
        self.llm_orchestrator = get_llm_orchestrator()
    
    async def analyze_earnings_calls(
        self,
        ticker: str,
        days_back: int = 90,
        max_calls: int = 5
    ) -> Dict[str, Any]:
        """
        Analyze earnings calls for a ticker
        
        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back
            max_calls: Maximum number of calls to analyze
            
        Returns:
            Comprehensive earnings call analysis
        """
        cache_key = f"earnings_call_analysis:{ticker}:{days_back}:{max_calls}"
        
        # Check cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Retrieved earnings call analysis from cache for {ticker}")
            return cached_result
        
        try:
            # Get transcripts from all sources
            all_transcripts = []
            for source in self.sources:
                try:
                    transcripts = await source.get_transcripts(ticker, days_back)
                    all_transcripts.extend(transcripts)
                    logger.info(f"Retrieved {len(transcripts)} transcripts from {source.get_source_name()}")
                except Exception as e:
                    logger.warning(f"Error getting transcripts from {source.get_source_name()}: {e}")
                    continue
            
            # Deduplicate and sort by date
            unique_transcripts = self._deduplicate_transcripts(all_transcripts)
            unique_transcripts.sort(key=lambda x: x.call_date, reverse=True)
            
            # Limit to most recent calls
            recent_transcripts = unique_transcripts[:max_calls]
            
            if not recent_transcripts:
                return {
                    "ticker": ticker,
                    "total_calls": 0,
                    "analysis_period": f"{days_back} days",
                    "message": "No earnings call transcripts found",
                    "analysis_date": datetime.now().isoformat()
                }
            
            # Analyze each call
            call_analyses = []
            for transcript in recent_transcripts:
                try:
                    analysis = await self._analyze_single_call(transcript)
                    call_analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Error analyzing call {transcript.call_id}: {e}")
                    continue
            
            # Aggregate analysis
            aggregated_analysis = self._aggregate_analyses(call_analyses)
            
            # Add metadata
            aggregated_analysis.update({
                "ticker": ticker,
                "total_calls": len(recent_transcripts),
                "analysis_period": f"{days_back} days",
                "sources_used": [source.get_source_name() for source in self.sources],
                "analysis_date": datetime.now().isoformat()
            })
            
            # Cache results for 6 hours
            await self.cache.set(cache_key, aggregated_analysis, ttl=21600)
            
            logger.info(f"Completed earnings call analysis for {ticker}: {len(call_analyses)} calls analyzed")
            return aggregated_analysis
        
        except Exception as e:
            logger.error(f"Error analyzing earnings calls for {ticker}: {e}")
            return {
                "ticker": ticker,
                "error": str(e),
                "analysis_date": datetime.now().isoformat()
            }
    
    def _deduplicate_transcripts(self, transcripts: List[EarningsCall]) -> List[EarningsCall]:
        """Remove duplicate transcripts based on date and quarter"""
        seen = set()
        unique_transcripts = []
        
        for transcript in transcripts:
            # Create a key based on date and quarter
            key = (transcript.call_date.date(), transcript.quarter)
            
            if key not in seen:
                seen.add(key)
                unique_transcripts.append(transcript)
        
        return unique_transcripts
    
    async def _analyze_single_call(self, transcript: EarningsCall) -> CallAnalysis:
        """Analyze a single earnings call"""
        
        # Get transcript text if not already available
        if not transcript.transcript_text:
            transcript.transcript_text = await self._fetch_transcript_text(transcript)
        
        if not transcript.transcript_text:
            # Return empty analysis if no transcript text
            return CallAnalysis(
                ticker=transcript.ticker,
                call_date=transcript.call_date,
                quarter=transcript.quarter,
                overall_sentiment=0.0,
                management_tone="unknown",
                confidence_score=0.0
            )
        
        # Perform sentiment analysis
        sentiment_analysis = await self._analyze_sentiment(transcript.transcript_text)
        
        # Extract guidance
        guidance_analysis = await self._extract_guidance(transcript.transcript_text)
        
        # Analyze Q&A session
        qa_analysis = await self._analyze_qa_session(transcript.transcript_text)
        
        # Extract key topics
        topics_analysis = await self._extract_key_topics(transcript.transcript_text)
        
        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(transcript.transcript_text)
        
        return CallAnalysis(
            ticker=transcript.ticker,
            call_date=transcript.call_date,
            quarter=transcript.quarter,
            overall_sentiment=sentiment_analysis["sentiment"],
            management_tone=sentiment_analysis["tone"],
            confidence_score=sentiment_analysis["confidence"],
            revenue_guidance=guidance_analysis.get("revenue"),
            earnings_guidance=guidance_analysis.get("earnings"),
            margin_guidance=guidance_analysis.get("margins"),
            capex_guidance=guidance_analysis.get("capex"),
            analyst_questions=qa_analysis.get("questions", []),
            management_responses=qa_analysis.get("responses", []),
            defensiveness_score=qa_analysis.get("defensiveness", 0.0),
            topics_avoided=qa_analysis.get("topics_avoided", []),
            key_topics=topics_analysis.get("topics", []),
            concerns_raised=topics_analysis.get("concerns", []),
            new_initiatives=topics_analysis.get("initiatives", []),
            call_quality_score=quality_metrics["quality"],
            information_density=quality_metrics["density"],
            transparency_score=quality_metrics["transparency"],
            data_sources=[transcript.transcript_url]
        )
    
    async def _fetch_transcript_text(self, transcript: EarningsCall) -> Optional[str]:
        """Fetch transcript text from URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(transcript.transcript_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract transcript text (varies by source)
                        transcript_text = ""
                        
                        # Common selectors for transcript content
                        selectors = [
                            '.transcript-content',
                            '.article-content',
                            '.transcript',
                            '[data-testid="transcript-content"]',
                            '.content'
                        ]
                        
                        for selector in selectors:
                            content = soup.select_one(selector)
                            if content:
                                transcript_text = content.get_text(separator='\n', strip=True)
                                break
                        
                        return transcript_text if transcript_text else None
        
        except Exception as e:
            logger.warning(f"Error fetching transcript text: {e}")
            return None
    
    async def _analyze_sentiment(self, transcript_text: str) -> Dict[str, Any]:
        """Analyze sentiment and tone of the transcript"""
        try:
            # Use LLM for sentiment analysis
            prompt = f"""
            Analyze the sentiment and tone of this earnings call transcript.
            
            Transcript:
            {transcript_text[:2000]}...
            
            Provide:
            1. Overall sentiment score (-1 to 1, where -1 is very negative, 0 is neutral, 1 is very positive)
            2. Management tone (bullish, cautious, defensive, optimistic, neutral)
            3. Confidence level (0 to 1, where 1 is very confident)
            4. Key sentiment drivers (2-3 bullet points)
            
            Format as JSON:
            {{
                "sentiment": 0.5,
                "tone": "optimistic",
                "confidence": 0.8,
                "drivers": ["Strong revenue growth", "Positive outlook", "Market expansion"]
            }}
            """
            
            response = await self.llm_orchestrator.generate_response(
                task_type=TaskType.SENTIMENT_ANALYSIS,
                prompt=prompt,
                context={"transcript_length": len(transcript_text)},
                complexity=TaskComplexity.MODERATE
            )
            
            if response.content:
                try:
                    # Parse JSON response
                    import json
                    result = json.loads(response.content)
                    return {
                        "sentiment": result.get("sentiment", 0.0),
                        "tone": result.get("tone", "neutral"),
                        "confidence": result.get("confidence", 0.5),
                        "drivers": result.get("drivers", [])
                    }
                except json.JSONDecodeError:
                    pass
            
            # Fallback to TextBlob sentiment analysis (if available)
            if NLP_PROCESSING_AVAILABLE:
                blob = TextBlob(transcript_text)
                sentiment_score = blob.sentiment.polarity
            else:
                sentiment_score = 0.0
            
            return {
                "sentiment": sentiment_score,
                "tone": "bullish" if sentiment_score > 0.1 else "cautious" if sentiment_score < -0.1 else "neutral",
                "confidence": 0.6,
                "drivers": ["Automated sentiment analysis"]
            }
        
        except Exception as e:
            logger.warning(f"Error in sentiment analysis: {e}")
            return {
                "sentiment": 0.0,
                "tone": "unknown",
                "confidence": 0.0,
                "drivers": []
            }
    
    async def _extract_guidance(self, transcript_text: str) -> Dict[str, Any]:
        """Extract financial guidance from transcript"""
        try:
            # Use LLM to extract guidance
            prompt = f"""
            Extract financial guidance from this earnings call transcript.
            
            Transcript:
            {transcript_text[:3000]}...
            
            Look for:
            1. Revenue guidance (quarterly, annual)
            2. Earnings guidance (EPS, net income)
            3. Margin guidance (gross, operating, net margins)
            4. Capital expenditure guidance
            
            Format as JSON:
            {{
                "revenue": {{
                    "quarterly": "Q2 revenue guidance: $X-Y billion",
                    "annual": "Full year revenue guidance: $X-Y billion",
                    "growth_rate": "X% year-over-year growth"
                }},
                "earnings": {{
                    "eps": "Q2 EPS guidance: $X-Y",
                    "net_income": "Net income guidance: $X-Y billion"
                }},
                "margins": {{
                    "gross_margin": "Gross margin guidance: X%",
                    "operating_margin": "Operating margin guidance: X%"
                }},
                "capex": {{
                    "amount": "Capital expenditure guidance: $X-Y billion",
                    "focus_areas": ["Technology", "Infrastructure"]
                }}
            }}
            """
            
            response = await self.llm_orchestrator.generate_response(
                task_type=TaskType.DATA_EXTRACTION,
                prompt=prompt,
                context={"transcript_length": len(transcript_text)},
                complexity=TaskComplexity.MODERATE
            )
            
            if response.content:
                try:
                    import json
                    return json.loads(response.content)
                except json.JSONDecodeError:
                    pass
            
            # Fallback: simple pattern matching
            return self._extract_guidance_patterns(transcript_text)
        
        except Exception as e:
            logger.warning(f"Error extracting guidance: {e}")
            return {}
    
    def _extract_guidance_patterns(self, transcript_text: str) -> Dict[str, Any]:
        """Extract guidance using pattern matching"""
        guidance = {}
        
        # Revenue guidance patterns
        revenue_patterns = [
            r'revenue.*guidance.*?(\$[\d,\.]+[BMK]?)',
            r'guidance.*revenue.*?(\$[\d,\.]+[BMK]?)',
            r'expect.*revenue.*?(\$[\d,\.]+[BMK]?)'
        ]
        
        for pattern in revenue_patterns:
            match = re.search(pattern, transcript_text, re.IGNORECASE)
            if match:
                guidance["revenue"] = {"amount": match.group(1)}
                break
        
        return guidance
    
    async def _analyze_qa_session(self, transcript_text: str) -> Dict[str, Any]:
        """Analyze Q&A session for defensiveness and key topics"""
        try:
            # Use LLM to analyze Q&A session
            prompt = f"""
            Analyze the Q&A session from this earnings call transcript.
            
            Transcript:
            {transcript_text[:3000]}...
            
            Provide:
            1. Key analyst questions (top 3-5)
            2. Management response quality (defensive, open, evasive)
            3. Topics that management avoided or were evasive about
            4. Defensiveness score (0-1, where 1 is very defensive)
            
            Format as JSON:
            {{
                "questions": ["Question 1", "Question 2", "Question 3"],
                "responses": ["Response 1", "Response 2", "Response 3"],
                "defensiveness": 0.3,
                "topics_avoided": ["Topic 1", "Topic 2"]
            }}
            """
            
            response = await self.llm_orchestrator.generate_response(
                task_type=TaskType.SENTIMENT_ANALYSIS,
                prompt=prompt,
                context={"transcript_length": len(transcript_text)},
                complexity=TaskComplexity.MODERATE
            )
            
            if response.content:
                try:
                    import json
                    return json.loads(response.content)
                except json.JSONDecodeError:
                    pass
            
            # Fallback analysis
            return {
                "questions": [],
                "responses": [],
                "defensiveness": 0.5,
                "topics_avoided": []
            }
        
        except Exception as e:
            logger.warning(f"Error analyzing Q&A session: {e}")
            return {
                "questions": [],
                "responses": [],
                "defensiveness": 0.5,
                "topics_avoided": []
            }
    
    async def _extract_key_topics(self, transcript_text: str) -> Dict[str, Any]:
        """Extract key topics, concerns, and new initiatives"""
        try:
            # Use LLM to extract key topics
            prompt = f"""
            Extract key topics, concerns, and new initiatives from this earnings call transcript.
            
            Transcript:
            {transcript_text[:3000]}...
            
            Provide:
            1. Key topics discussed (top 5-7)
            2. Concerns or challenges raised
            3. New initiatives or strategic moves announced
            
            Format as JSON:
            {{
                "topics": ["Topic 1", "Topic 2", "Topic 3"],
                "concerns": ["Concern 1", "Concern 2"],
                "initiatives": ["Initiative 1", "Initiative 2"]
            }}
            """
            
            response = await self.llm_orchestrator.generate_response(
                task_type=TaskType.DATA_EXTRACTION,
                prompt=prompt,
                context={"transcript_length": len(transcript_text)},
                complexity=TaskComplexity.MODERATE
            )
            
            if response.content:
                try:
                    import json
                    return json.loads(response.content)
                except json.JSONDecodeError:
                    pass
            
            # Fallback: simple keyword extraction
            return self._extract_topics_keywords(transcript_text)
        
        except Exception as e:
            logger.warning(f"Error extracting key topics: {e}")
            return {
                "topics": [],
                "concerns": [],
                "initiatives": []
            }
    
    def _extract_topics_keywords(self, transcript_text: str) -> Dict[str, Any]:
        """Extract topics using keyword analysis"""
        # Common business topics
        topic_keywords = {
            "revenue": ["revenue", "sales", "top line"],
            "profitability": ["profit", "margin", "earnings", "bottom line"],
            "growth": ["growth", "expansion", "increase"],
            "market": ["market", "competition", "market share"],
            "technology": ["technology", "digital", "innovation"],
            "costs": ["cost", "expense", "efficiency"],
            "guidance": ["guidance", "outlook", "forecast"]
        }
        
        topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in transcript_text.lower() for keyword in keywords):
                topics.append(topic)
        
        return {
            "topics": topics[:5],
            "concerns": [],
            "initiatives": []
        }
    
    def _calculate_quality_metrics(self, transcript_text: str) -> Dict[str, float]:
        """Calculate call quality metrics"""
        # Simple quality metrics based on transcript characteristics
        word_count = len(transcript_text.split())
        
        # Quality score based on length and structure
        quality_score = min(1.0, word_count / 5000)  # Normalize to 5000 words
        
        # Information density (words per sentence)
        sentences = transcript_text.split('.')
        avg_words_per_sentence = word_count / max(len(sentences), 1)
        density_score = min(1.0, avg_words_per_sentence / 20)  # Normalize to 20 words/sentence
        
        # Transparency score (based on specific words)
        transparency_words = ["guidance", "outlook", "forecast", "expect", "plan"]
        transparency_count = sum(1 for word in transparency_words if word in transcript_text.lower())
        transparency_score = min(1.0, transparency_count / 10)  # Normalize to 10 mentions
        
        return {
            "quality": quality_score,
            "density": density_score,
            "transparency": transparency_score
        }
    
    def _aggregate_analyses(self, analyses: List[CallAnalysis]) -> Dict[str, Any]:
        """Aggregate multiple call analyses"""
        if not analyses:
            return {}
        
        # Calculate averages
        avg_sentiment = sum(a.overall_sentiment for a in analyses) / len(analyses)
        avg_confidence = sum(a.confidence_score for a in analyses) / len(analyses)
        avg_defensiveness = sum(a.defensiveness_score for a in analyses) / len(analyses)
        avg_quality = sum(a.call_quality_score for a in analyses) / len(analyses)
        
        # Aggregate guidance
        all_guidance = {
            "revenue": [],
            "earnings": [],
            "margins": [],
            "capex": []
        }
        
        for analysis in analyses:
            if analysis.revenue_guidance:
                all_guidance["revenue"].append(analysis.revenue_guidance)
            if analysis.earnings_guidance:
                all_guidance["earnings"].append(analysis.earnings_guidance)
            if analysis.margin_guidance:
                all_guidance["margins"].append(analysis.margin_guidance)
            if analysis.capex_guidance:
                all_guidance["capex"].append(analysis.capex_guidance)
        
        # Aggregate topics
        all_topics = []
        all_concerns = []
        all_initiatives = []
        
        for analysis in analyses:
            all_topics.extend(analysis.key_topics)
            all_concerns.extend(analysis.concerns_raised)
            all_initiatives.extend(analysis.new_initiatives)
        
        # Get most common items
        from collections import Counter
        common_topics = [item for item, count in Counter(all_topics).most_common(5)]
        common_concerns = [item for item, count in Counter(all_concerns).most_common(3)]
        common_initiatives = [item for item, count in Counter(all_initiatives).most_common(3)]
        
        return {
            "aggregated_sentiment": {
                "overall_sentiment": avg_sentiment,
                "confidence_score": avg_confidence,
                "defensiveness_score": avg_defensiveness,
                "call_quality": avg_quality
            },
            "guidance_summary": all_guidance,
            "key_topics": common_topics,
            "common_concerns": common_concerns,
            "new_initiatives": common_initiatives,
            "individual_analyses": [
                {
                    "quarter": a.quarter,
                    "call_date": a.call_date.isoformat(),
                    "sentiment": a.overall_sentiment,
                    "tone": a.management_tone,
                    "defensiveness": a.defensiveness_score,
                    "quality_score": a.call_quality_score
                }
                for a in analyses
            ]
        }


# Main function for integration
async def analyze_earnings_calls(ticker: str, days_back: int = 90, max_calls: int = 5) -> Dict[str, Any]:
    """
    Main function to analyze earnings calls for a ticker
    
    Args:
        ticker: Stock ticker symbol
        days_back: Number of days to look back
        max_calls: Maximum number of calls to analyze
        
    Returns:
        Comprehensive earnings call analysis
    """
    analyzer = EarningsCallAnalyzer()
    return await analyzer.analyze_earnings_calls(ticker, days_back, max_calls)
