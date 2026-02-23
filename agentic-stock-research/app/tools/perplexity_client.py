"""
Perplexity API client for stock research
Provides fallback data fetching and enhanced recommendation generation
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
import asyncio

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
# Perplexity model for online search (real-time web access)
# Available models: sonar, sonar-pro, llama-3.1-8b-instant, llama-3.1-70b-instant, llama-3.1-70b-versatile
PERPLEXITY_MODEL = "sonar"  # Online search-enabled model


async def _perplexity_request(messages: list[Dict[str, str]], max_retries: int = 2) -> Optional[str]:
    """
    Make a request to Perplexity API with retry logic
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        max_retries: Maximum number of retry attempts
    
    Returns:
        Response content string or None if failed
    """
    settings = get_settings()
    api_key = getattr(settings, 'perplexity_api_key', None)
    
    if not api_key:
        logger.warning("Perplexity API key not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": messages
    }
    
    # Reduced timeout and retries for faster failure to prevent blocking analysis
    async with httpx.AsyncClient(timeout=15.0) as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(PERPLEXITY_API_URL, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return content
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = 2 ** attempt
                    logger.warning(f"Perplexity rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        return None
                        
            except Exception as e:
                logger.error(f"Perplexity request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None
    
    return None


def _extract_json_from_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from Perplexity response (may be wrapped in markdown code blocks)
    
    Args:
        response: Response string from Perplexity
    
    Returns:
        Parsed JSON dict or None if parsing fails
    """
    if not response:
        return None
    
    try:
        # Try direct JSON parse first
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON from markdown code blocks
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        elif "```" in response:
            # Try generic code block
            json_str = response.split("```")[1].split("```")[0].strip()
            if json_str.startswith("{"):
                return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        pass
    
    # Try finding JSON object in response
    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    logger.warning("Could not extract JSON from Perplexity response")
    return None


async def fetch_stock_data_perplexity(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch stock data from Perplexity API as fallback when Yahoo Finance fails
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Dict with stock data or None if failed
    """
    messages = [
        {
            "role": "system",
            "content": "You are a financial data assistant. Provide accurate stock market data in JSON format."
        },
        {
            "role": "user",
            "content": f"""Get the latest stock data and financial metrics for {ticker}. 
            Provide a JSON object with the following fields:
            - regularMarketPrice (current price)
            - marketCap (market capitalization)
            - trailingPE (P/E ratio)
            - priceToBook (P/B ratio)
            - trailingEps (EPS)
            - dividendYield (dividend yield as decimal, e.g., 0.02 for 2%)
            - fiftyTwoWeekHigh (52-week high)
            - fiftyTwoWeekLow (52-week low)
            - totalRevenue (total revenue)
            - netIncomeToCommon (net income)
            - returnOnEquity (ROE as decimal)
            - debtToEquity (debt to equity ratio)
            - sector (company sector)
            - industry (company industry)
            - longName (company name)
            
            Format as valid JSON only."""
        }
    ]
    
    response = await _perplexity_request(messages)
    if not response:
        return None
    
    # Extract and parse JSON
    data = _extract_json_from_response(response)
    if data:
        data["source"] = "perplexity"
        logger.info(f"Successfully fetched stock data from Perplexity for {ticker}")
        return data
    
    return None


async def get_final_recommendation_perplexity(
    ticker: str,
    analysis_summary: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Generate final investment recommendation using Perplexity API
    
    Args:
        ticker: Stock ticker symbol
        analysis_summary: Complete analysis summary including metrics, ratios, trends, etc.
    
    Returns:
        Dict with 'recommendation' (BUY/HOLD/SELL) and 'reasoning' (explanation)
    """
    # Format analysis summary for Perplexity
    analysis_text = json.dumps(analysis_summary, indent=2, default=str)
    
    messages = [
        {
            "role": "system",
            "content": "You are a professional equity research analyst with expertise in fundamental analysis, technical analysis, and market sentiment. Provide clear, actionable investment recommendations based on comprehensive data analysis."
        },
        {
            "role": "user",
            "content": f"""Based on the following comprehensive stock analysis for {ticker}, provide a clear investment recommendation.

Stock Analysis Data:
{analysis_text}

Requirements:
1. Give a clear recommendation: BUY, HOLD, or SELL
2. Explain your reasoning concisely in 150-250 words
3. Consider all factors: valuation metrics, financial health, growth prospects, technical indicators, sentiment, and risk factors
4. Highlight the most important factors driving your recommendation

Respond in JSON format with exactly these fields:
{{
    "recommendation": "BUY" or "HOLD" or "SELL",
    "reasoning": "Your detailed explanation here",
    "confidence": "High" or "Medium" or "Low",
    "key_factors": ["factor1", "factor2", "factor3"]
}}"""
        }
    ]
    
    response = await _perplexity_request(messages)
    if not response:
        return None
    
    # Extract and parse JSON
    result = _extract_json_from_response(response)
    if result:
        logger.info(f"Generated Perplexity recommendation for {ticker}: {result.get('recommendation', 'Unknown')}")
        return result
    
    # Fallback: try to extract recommendation from plain text
    if response:
        recommendation = "HOLD"
        if "buy" in response.lower() and "sell" not in response.lower():
            recommendation = "BUY"
        elif "sell" in response.lower():
            recommendation = "SELL"
        
        return {
            "recommendation": recommendation,
            "reasoning": response[:500],  # First 500 chars
            "confidence": "Medium",
            "key_factors": []
        }
    
    return None

