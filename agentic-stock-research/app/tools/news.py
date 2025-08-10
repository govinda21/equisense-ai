from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncio
import logging
import httpx
from datetime import datetime, timedelta
import yfinance as yf

from app.utils.retry import retry_async, circuit_breaker_async

logger = logging.getLogger(__name__)


async def fetch_real_news(ticker: str, max_articles: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch real-time financial news for a given ticker from multiple sources.
    """
    
    @retry_async(max_retries=2, base_delay=0.5, exceptions=(Exception,))
    async def _fetch_yfinance_news() -> List[Dict[str, Any]]:
        """Fetch news from Yahoo Finance via yfinance with retry logic"""
        def _get_yf_news():
            try:
                logger.debug(f"Fetching news for {ticker} from Yahoo Finance")
                stock = yf.Ticker(ticker)
                news = getattr(stock, 'news', [])
                
                if not news:
                    logger.warning(f"No news articles found for {ticker}")
                    return []
                
                # Extract the nested content structure
                processed_news = []
                for article in news[:max_articles]:
                    if isinstance(article, dict) and 'content' in article:
                        content = article['content']
                        processed_article = {
                            'title': content.get('title', ''),
                            'summary': content.get('summary', content.get('description', '')),
                            'link': content.get('canonicalUrl', {}).get('url', ''),
                            'publisher': content.get('provider', {}).get('displayName', 'Yahoo Finance'),
                            'providerPublishTime': content.get('pubDate', ''),
                            'raw': article  # Keep original for debugging
                        }
                        processed_news.append(processed_article)
                
                logger.debug(f"Successfully fetched {len(processed_news)} news articles for {ticker}")
                return processed_news
                
            except Exception as e:
                logger.error(f"Failed to fetch news for {ticker}: {e}")
                raise  # Re-raise for retry logic
        
        return await asyncio.to_thread(_get_yf_news)
    
    async def _fetch_google_news() -> List[Dict[str, Any]]:
        """Fetch news from Google Finance RSS (no API key required)"""
        try:
            # Extract base ticker symbol without exchange suffix
            base_ticker = ticker.split('.')[0]
            
            # Google Finance RSS URL
            url = f"https://news.google.com/rss/search?q={base_ticker}+stock&hl=en-US&gl=US&ceid=US:en"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    # Parse RSS feed (simplified parsing)
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(response.content)
                    
                    articles = []
                    for item in root.findall('.//item')[:3]:  # Limit to 3 articles
                        title = item.find('title')
                        link = item.find('link')
                        pub_date = item.find('pubDate')
                        description = item.find('description')
                        
                        if title is not None and title.text:
                            articles.append({
                                'title': title.text,
                                'summary': description.text if description is not None else '',
                                'link': link.text if link is not None else '',
                                'publisher': 'Google News',
                                'providerPublishTime': pub_date.text if pub_date is not None else '',
                                'raw': {'source': 'google_news'}
                            })
                    
                    logger.debug(f"Google News found {len(articles)} articles for {ticker}")
                    return articles
                    
            return []
        except Exception as e:
            logger.debug(f"Google News fetch failed for {ticker}: {e}")
            return []
    
    async def _fetch_alpha_vantage_news() -> List[Dict[str, Any]]:
        """Fetch news from Alpha Vantage (free tier available)"""
        try:
            # Note: Alpha Vantage requires API key for production use
            # For now, return empty to avoid API key requirement
            return []
        except Exception:
            return []
    
    async def _fetch_indian_stock_news() -> List[Dict[str, Any]]:
        """Fetch news from Indian financial sources for .NS tickers"""
        try:
            if not ticker.endswith('.NS'):
                return []
            
            # Extract base ticker for Indian stocks
            base_ticker = ticker.replace('.NS', '')
            
            # Try Economic Times and MoneyControl RSS feeds
            sources = [
                f"https://economictimes.indiatimes.com/markets/stocks/rss",
                f"https://www.moneycontrol.com/rss/latestnews.xml"
            ]
            
            articles = []
            async with httpx.AsyncClient(timeout=10.0) as client:
                for source_url in sources:
                    try:
                        response = await client.get(source_url)
                        if response.status_code == 200:
                            # Simple RSS parsing for Indian financial news
                            import xml.etree.ElementTree as ET
                            root = ET.fromstring(response.content)
                            
                            for item in root.findall('.//item')[:2]:  # Limit to 2 per source
                                title = item.find('title')
                                link = item.find('link') 
                                description = item.find('description')
                                pub_date = item.find('pubDate')
                                
                                if title is not None and title.text:
                                    # Filter for relevant stock content
                                    title_text = title.text.lower()
                                    if any(keyword in title_text for keyword in [base_ticker.lower(), 'stock', 'share', 'market']):
                                        articles.append({
                                            'title': title.text,
                                            'summary': description.text if description is not None else '',
                                            'link': link.text if link is not None else '',
                                            'publisher': 'Indian Financial News',
                                            'providerPublishTime': pub_date.text if pub_date is not None else '',
                                            'raw': {'source': 'indian_financial'}
                                        })
                                        
                    except Exception as e:
                        logger.debug(f"Failed to fetch from {source_url}: {e}")
                        continue
            
            logger.debug(f"Indian financial sources found {len(articles)} articles for {ticker}")
            return articles
            
        except Exception as e:
            logger.debug(f"Indian financial news fetch failed for {ticker}: {e}")
            return []
    
    # Multi-source news fetching strategy
    all_articles = []
    
    # Primary source: Yahoo Finance
    try:
        yf_articles = await _fetch_yfinance_news()
        all_articles.extend(yf_articles)
        logger.debug(f"Yahoo Finance provided {len(yf_articles)} articles for {ticker}")
    except Exception as e:
        logger.debug(f"Yahoo Finance failed for {ticker}: {e}")
    
    # If we need more articles, try additional sources
    if len(all_articles) < 3:
        # For Indian stocks, try Indian financial sources
        if ticker.endswith('.NS'):
            try:
                indian_articles = await _fetch_indian_stock_news()
                all_articles.extend(indian_articles)
                logger.debug(f"Indian sources provided {len(indian_articles)} articles for {ticker}")
            except Exception as e:
                logger.debug(f"Indian financial sources failed for {ticker}: {e}")
        
        # Try Google News as fallback
        if len(all_articles) < 2:
            try:
                google_articles = await _fetch_google_news()
                all_articles.extend(google_articles)
                logger.debug(f"Google News provided {len(google_articles)} articles for {ticker}")
            except Exception as e:
                logger.debug(f"Google News failed for {ticker}: {e}")
    
    # Remove duplicates based on title similarity
    articles = _deduplicate_articles(all_articles)
    
    # Log final results
    if not articles:
        logger.info(f"No news articles found for {ticker} from any source")
    elif len(articles) < 3:
        logger.debug(f"Found {len(articles)} articles for {ticker}, could benefit from additional sources")
    else:
        logger.debug(f"Successfully found {len(articles)} articles for {ticker}")
    
    # Standardize article format
    standardized_articles = []
    for article in articles:
        try:
            standardized_article = {
                'title': article.get('title', ''),
                'summary': article.get('summary', ''),
                'url': article.get('link', ''),
                'source': article.get('publisher', 'Yahoo Finance'),
                'published_at': _parse_timestamp(article.get('providerPublishTime')),
                'raw': article  # Keep original for debugging
            }
            
            # Only include articles with meaningful content
            if standardized_article['title'] and len(standardized_article['title']) > 10:
                standardized_articles.append(standardized_article)
                
        except Exception:
            continue
    
    return standardized_articles[:max_articles]


def _deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate articles based on title similarity"""
    if not articles:
        return []
    
    unique_articles = []
    seen_titles = set()
    
    for article in articles:
        title = article.get('title', '').lower().strip()
        if title and title not in seen_titles:
            # Check for similar titles (simple similarity check)
            is_duplicate = False
            for seen_title in seen_titles:
                # Simple similarity: if titles share >70% of words, consider duplicate
                title_words = set(title.split())
                seen_words = set(seen_title.split())
                if len(title_words & seen_words) / max(len(title_words), len(seen_words)) > 0.7:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_articles.append(article)
                seen_titles.add(title)
    
    return unique_articles


def _parse_timestamp(timestamp: Optional[Any]) -> str:
    """Convert timestamp (Unix int or ISO string) to readable date"""
    try:
        if timestamp:
            # Handle both Unix timestamp (int) and ISO string formats
            if isinstance(timestamp, int):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                # Parse ISO format like "2025-06-09T20:06:19Z"
                if 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(timestamp)
            else:
                return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


async def get_news_headlines_and_summaries(ticker: str, max_articles: int = 5) -> tuple[List[str], str]:
    """
    Get news headlines and a combined summary for sentiment analysis.
    Returns: (headlines_list, combined_summary)
    """
    articles = await fetch_real_news(ticker, max_articles)
    
    if not articles:
        # Fallback: return a neutral message instead of generating fake news
        fallback_headline = f"Limited news coverage available for {ticker} at this time."
        return [fallback_headline], fallback_headline
    
    # Extract headlines and summaries
    headlines = []
    summaries = []
    
    for article in articles:
        if article['title']:
            headlines.append(article['title'])
        
        if article['summary']:
            # Limit summary length to avoid overwhelming the LLM
            summary = article['summary'][:500] + "..." if len(article['summary']) > 500 else article['summary']
            summaries.append(summary)
    
    # Combine summaries into a coherent text for analysis
    combined_text = " ".join(summaries) if summaries else " ".join(headlines)
    
    return headlines, combined_text


async def get_recent_news_summary(ticker: str) -> Dict[str, Any]:
    """
    Get a structured summary of recent news for a ticker.
    """
    articles = await fetch_real_news(ticker)
    
    if not articles:
        return {
            'summary': f"No recent news available for {ticker}",
            'article_count': 0,
            'latest_date': None,
            'sources': [],
            'articles': []
        }
    
    # Get unique sources
    sources = list(set(article['source'] for article in articles if article['source']))
    
    # Get latest article date
    latest_date = None
    if articles:
        try:
            latest_date = articles[0]['published_at']  # Assuming sorted by recency
        except Exception:
            latest_date = datetime.now().strftime('%Y-%m-%d')
    
    # Create summary
    headlines = [article['title'] for article in articles if article['title']]
    summary_text = f"Recent news for {ticker}: " + "; ".join(headlines[:3])
    if len(headlines) > 3:
        summary_text += f" and {len(headlines) - 3} more articles"
    
    return {
        'summary': summary_text,
        'article_count': len(articles),
        'latest_date': latest_date,
        'sources': sources,
        'articles': articles[:3]  # Return top 3 for display
    }
