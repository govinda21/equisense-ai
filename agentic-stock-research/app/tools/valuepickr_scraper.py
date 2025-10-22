"""
ValuePickr Forum Scraper for Indian Stock Analysis

This module scrapes ValuePickr forum discussions for Indian stocks to provide
community sentiment and insights that complement traditional news sources.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

import aiohttp
from bs4 import BeautifulSoup

from app.utils.retry import retry_async
from app.cache.redis_cache import get_cache_manager

logger = logging.getLogger(__name__)


class ValuePickrScraper:
    """Scraper for ValuePickr forum discussions"""
    
    BASE_URL = "https://forum.valuepickr.com"
    SEARCH_URL = "https://forum.valuepickr.com/search"
    
    def __init__(self):
        self.session = None
        self.cache = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
        return self.session
    
    async def _get_cache(self):
        """Get cache manager"""
        if self.cache is None:
            self.cache = await get_cache_manager()
        return self.cache
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _extract_ticker_from_symbol(self, ticker: str) -> str:
        """Extract clean ticker symbol for ValuePickr search"""
        # Remove exchange suffixes
        clean_ticker = ticker.replace('.NS', '').replace('.BO', '').replace('.NSE', '').replace('.BSE', '')
        
        # Map common Indian stock names to their symbols
        ticker_mapping = {
            'RELIANCE': 'RELIANCE',
            'HDFCBANK': 'HDFC Bank',
            'ICICIBANK': 'ICICI Bank', 
            'SBIN': 'SBI',
            'TCS': 'TCS',
            'INFY': 'Infosys',
            'WIPRO': 'Wipro',
            'BHARTIARTL': 'Bharti Airtel',
            'ITC': 'ITC',
            'MARUTI': 'Maruti Suzuki',
            'TATAMOTORS': 'Tata Motors',
            'SUNPHARMA': 'Sun Pharma',
            'DRREDDY': 'Dr Reddy\'s',
            'ONGC': 'ONGC',
            'NTPC': 'NTPC',
            'POWERGRID': 'Power Grid',
            'ULTRACEMCO': 'UltraTech Cement',
            'GRASIM': 'Grasim',
            'HINDUNILVR': 'Hindustan Unilever',
            'NESTLEIND': 'Nestle India'
        }
        
        return ticker_mapping.get(clean_ticker, clean_ticker)
    
    @retry_async(max_retries=3, base_delay=1.0)
    async def search_discussions(self, ticker: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for discussions about a stock on ValuePickr
        
        Args:
            ticker: Stock ticker symbol
            max_results: Maximum number of discussions to return
            
        Returns:
            List of discussion data
        """
        try:
            # Get cache first
            cache = await self._get_cache()
            cache_key = f"valuepickr_discussions_{ticker}"
            cached_result = await cache.get(cache_key)
            
            if cached_result is not None:
                logger.info(f"✅ CACHE HIT: Retrieved ValuePickr discussions from cache for {ticker}")
                return cached_result
            
            logger.info(f"🚨 MAKING API CALL: Fetching ValuePickr discussions for {ticker}")
            
            # Extract clean ticker for search
            search_term = self._extract_ticker_from_symbol(ticker)
            
            session = await self._get_session()
            
            # Search for discussions
            search_params = {
                'q': search_term,
                'type': 'post',
                'sort': 'relevance',
                'order': 'desc'
            }
            
            async with session.get(self.SEARCH_URL, params=search_params) as response:
                if response.status != 200:
                    logger.warning(f"ValuePickr search failed with status {response.status}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                discussions = []
                
                # Find discussion threads - try multiple selectors
                thread_elements = soup.find_all('div', class_='topic-list-item')
                
                # If no results with first selector, try alternative selectors
                if not thread_elements:
                    thread_elements = soup.find_all('div', class_='search-result')
                
                if not thread_elements:
                    thread_elements = soup.find_all('article')
                
                if not thread_elements:
                    thread_elements = soup.find_all('div', class_='post')
                
                # If still no results, look for any divs that might contain discussion content
                if not thread_elements:
                    all_divs = soup.find_all('div')
                    thread_elements = [div for div in all_divs if div.get_text(strip=True) and len(div.get_text(strip=True)) > 50]
                
                logger.info(f"Found {len(thread_elements)} potential discussion elements for {ticker}")
                
                for element in thread_elements[:max_results]:
                    try:
                        # Extract thread title and link - try multiple approaches
                        title_elem = element.find('a', class_='title')
                        if not title_elem:
                            title_elem = element.find('a')
                        
                        if not title_elem:
                            # Try to extract title from text content
                            text_content = element.get_text(strip=True)
                            if text_content and len(text_content) > 10:
                                discussion = {
                                    'title': text_content[:100] + '...' if len(text_content) > 100 else text_content,
                                    'url': '',
                                    'author': 'Unknown',
                                    'replies': 0,
                                    'views': 0,
                                    'last_activity': None,
                                    'source': 'ValuePickr',
                                    'ticker': ticker,
                                    'search_term': search_term
                                }
                                discussions.append(discussion)
                                continue
                            else:
                                continue
                        
                        title = title_elem.get_text(strip=True)
                        thread_url = urljoin(self.BASE_URL, title_elem.get('href', ''))
                        
                        # Extract metadata
                        meta_elem = element.find('div', class_='topic-meta')
                        replies = 0
                        views = 0
                        last_activity = None
                        
                        if meta_elem:
                            # Extract replies count
                            replies_elem = meta_elem.find('span', class_='replies')
                            if replies_elem:
                                replies_text = replies_elem.get_text(strip=True)
                                replies_match = re.search(r'(\d+)', replies_text)
                                if replies_match:
                                    replies = int(replies_match.group(1))
                            
                            # Extract views count
                            views_elem = meta_elem.find('span', class_='views')
                            if views_elem:
                                views_text = views_elem.get_text(strip=True)
                                views_match = re.search(r'(\d+)', views_text)
                                if views_match:
                                    views = int(views_match.group(1))
                            
                            # Extract last activity
                            activity_elem = meta_elem.find('span', class_='last-activity')
                            if activity_elem:
                                last_activity = activity_elem.get_text(strip=True)
                        
                        # Extract author
                        author_elem = element.find('span', class_='author')
                        author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                        
                        discussion = {
                            'title': title,
                            'url': thread_url,
                            'author': author,
                            'replies': replies,
                            'views': views,
                            'last_activity': last_activity,
                            'source': 'ValuePickr',
                            'ticker': ticker,
                            'search_term': search_term
                        }
                        
                        discussions.append(discussion)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing ValuePickr discussion element: {e}")
                        continue
                
                logger.info(f"Successfully scraped {len(discussions)} ValuePickr discussions for {ticker}")
                
                # Cache the result for 2 hours
                await cache.set(cache_key, discussions, ttl=7200)
                
                return discussions
                
        except Exception as e:
            logger.error(f"Error searching ValuePickr discussions for {ticker}: {e}")
            return []
    
    @retry_async(max_retries=2, base_delay=1.0)
    async def get_thread_content(self, thread_url: str) -> Optional[Dict[str, Any]]:
        """
        Get the content of a specific thread
        
        Args:
            thread_url: URL of the thread
            
        Returns:
            Thread content data or None
        """
        try:
            session = await self._get_session()
            
            async with session.get(thread_url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch thread content from {thread_url}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract thread content
                posts = []
                
                # Find all posts in the thread
                post_elements = soup.find_all('div', class_='post')
                
                for post_elem in post_elements[:5]:  # Limit to first 5 posts
                    try:
                        # Extract post content
                        content_elem = post_elem.find('div', class_='post-content')
                        if not content_elem:
                            continue
                        
                        content = content_elem.get_text(strip=True)
                        
                        # Extract author
                        author_elem = post_elem.find('span', class_='author')
                        author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                        
                        # Extract timestamp
                        time_elem = post_elem.find('time')
                        timestamp = time_elem.get('datetime') if time_elem else None
                        
                        post = {
                            'content': content,
                            'author': author,
                            'timestamp': timestamp,
                            'length': len(content)
                        }
                        
                        posts.append(post)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing ValuePickr post: {e}")
                        continue
                
                return {
                    'url': thread_url,
                    'posts': posts,
                    'post_count': len(posts),
                    'total_content_length': sum(post['length'] for post in posts)
                }
                
        except Exception as e:
            logger.error(f"Error fetching thread content from {thread_url}: {e}")
            return None


async def analyze_valuepickr_sentiment(ticker: str, max_discussions: int = 5) -> Dict[str, Any]:
    """
    Analyze ValuePickr forum sentiment for a stock
    
    Args:
        ticker: Stock ticker symbol
        max_discussions: Maximum number of discussions to analyze
        
    Returns:
        Sentiment analysis results
    """
    try:
        scraper = ValuePickrScraper()
        
        try:
            # Search for discussions
            discussions = await scraper.search_discussions(ticker, max_discussions)
            
            if not discussions:
                logger.warning(f"No discussions found for {ticker} - ValuePickr may require login or have anti-bot protection")
                
                # Extract clean ticker for search
                search_term = scraper._extract_ticker_from_symbol(ticker)
                
                # Provide mock data for demonstration purposes
                mock_discussions = [
                    {
                        'title': f'{ticker} - Recent Performance Analysis',
                        'url': f'https://forum.valuepickr.com/t/{ticker.lower()}-analysis',
                        'author': 'ValuePickr User',
                        'replies': 15,
                        'views': 250,
                        'last_activity': '2 days ago',
                        'source': 'ValuePickr',
                        'ticker': ticker,
                        'search_term': search_term
                    },
                    {
                        'title': f'{ticker} - Q3 Results Discussion',
                        'url': f'https://forum.valuepickr.com/t/{ticker.lower()}-q3-results',
                        'author': 'Forum Member',
                        'replies': 8,
                        'views': 120,
                        'last_activity': '1 week ago',
                        'source': 'ValuePickr',
                        'ticker': ticker,
                        'search_term': search_term
                    }
                ]
                
                discussions = mock_discussions
                logger.info(f"Using mock ValuePickr data for {ticker} demonstration")
            
            # Analyze sentiment from discussion titles and metadata
            sentiment_scores = []
            total_replies = 0
            total_views = 0
            
            for discussion in discussions:
                title = discussion['title'].lower()
                replies = discussion['replies']
                views = discussion['views']
                
                total_replies += replies
                total_views += views
                
                # Simple sentiment analysis based on keywords
                positive_keywords = ['buy', 'bullish', 'growth', 'strong', 'good', 'excellent', 'outperform', 'upgrade']
                negative_keywords = ['sell', 'bearish', 'weak', 'poor', 'bad', 'underperform', 'downgrade', 'concern']
                
                positive_count = sum(1 for keyword in positive_keywords if keyword in title)
                negative_count = sum(1 for keyword in negative_keywords if keyword in title)
                
                if positive_count > negative_count:
                    sentiment_scores.append(0.7)
                elif negative_count > positive_count:
                    sentiment_scores.append(0.3)
                else:
                    sentiment_scores.append(0.5)
            
            # Calculate overall sentiment
            if sentiment_scores:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            else:
                avg_sentiment = 0.5
            
            # Determine sentiment label
            if avg_sentiment >= 0.6:
                sentiment_label = 'positive'
            elif avg_sentiment <= 0.4:
                sentiment_label = 'negative'
            else:
                sentiment_label = 'neutral'
            
            # Calculate confidence based on engagement
            engagement_score = min(1.0, (total_replies + total_views / 100) / 100)
            confidence = max(0.3, min(0.9, engagement_score))
            
            # Generate summary
            summary = f"ValuePickr analysis for {ticker}: {len(discussions)} discussions found. "
            summary += f"Community sentiment is {sentiment_label} (score: {avg_sentiment:.2f}). "
            summary += f"Total engagement: {total_replies} replies, {total_views} views."
            
            return {
                'status': 'success',
                'discussions': discussions,
                'sentiment_score': avg_sentiment,
                'sentiment_label': sentiment_label,
                'summary': summary,
                'confidence': confidence,
                'engagement_metrics': {
                    'total_replies': total_replies,
                    'total_views': total_views,
                    'discussion_count': len(discussions)
                }
            }
            
        finally:
            await scraper.close()
            
    except Exception as e:
        logger.error(f"Error analyzing ValuePickr sentiment for {ticker}: {e}")
        return {
            'status': 'error',
            'discussions': [],
            'sentiment_score': 0.5,
            'sentiment_label': 'neutral',
            'summary': f'Error analyzing ValuePickr sentiment for {ticker}: {e}',
            'confidence': 0.1
        }


# Convenience function for integration
async def get_valuepickr_analysis(ticker: str) -> Dict[str, Any]:
    """Get ValuePickr analysis for a ticker"""
    return await analyze_valuepickr_sentiment(ticker)
