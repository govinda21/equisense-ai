"""
Test ticker configurations and mappings for validation suite
"""

from typing import Dict, List

# Ticker to Screener.in URL mapping
TICKER_TO_SCREENER_ID = {
    "HDFCBANK.NS": "hdfc-bank",
    "ICICIBANK.NS": "icici-bank",
    "TCS.NS": "tcs",
    "INFY.NS": "infosys",
    "RELIANCE.NS": "reliance-industries",
    "HINDUNILVR.NS": "hindustan-unilever",
    "ITC.NS": "itc",
    "MARUTI.NS": "maruti-suzuki",
    "AXISBANK.NS": "axis-bank",
    "SBIN.NS": "sbi",
    "WIPRO.NS": "wipro",
    "BHARTIARTL.NS": "bharti-airtel",
}

# Test ticker categories
TEST_TICKERS = {
    "indian_banks": [
        {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "screener_id": "hdfc-bank", "sector": "Banking"},
        {"ticker": "ICICIBANK.NS", "name": "ICICI Bank", "screener_id": "icici-bank", "sector": "Banking"},
        {"ticker": "AXISBANK.NS", "name": "Axis Bank", "screener_id": "axis-bank", "sector": "Banking"},
        {"ticker": "SBIN.NS", "name": "State Bank of India", "screener_id": "sbi", "sector": "Banking"},
    ],
    "indian_it": [
        {"ticker": "TCS.NS", "name": "TCS", "screener_id": "tcs", "sector": "IT Services"},
        {"ticker": "INFY.NS", "name": "Infosys", "screener_id": "infosys", "sector": "IT Services"},
        {"ticker": "WIPRO.NS", "name": "Wipro", "screener_id": "wipro", "sector": "IT Services"},
    ],
    "indian_fmcg": [
        {"ticker": "HINDUNILVR.NS", "name": "Hindustan Unilever", "screener_id": "hindustan-unilever", "sector": "FMCG"},
        {"ticker": "ITC.NS", "name": "ITC", "screener_id": "itc", "sector": "FMCG"},
    ],
    "indian_auto": [
        {"ticker": "MARUTI.NS", "name": "Maruti Suzuki", "screener_id": "maruti-suzuki", "sector": "Automobiles"},
    ],
    "indian_telecom": [
        {"ticker": "BHARTIARTL.NS", "name": "Bharti Airtel", "screener_id": "bharti-airtel", "sector": "Telecom"},
    ],
    "indian_conglomerate": [
        {"ticker": "RELIANCE.NS", "name": "Reliance Industries", "screener_id": "reliance-industries", "sector": "Conglomerate"},
    ],
}

# Daily test set - representative stocks across sectors
DAILY_TEST_SET = [
    "HDFCBANK.NS",    # Banking
    "ICICIBANK.NS",   # Banking
    "TCS.NS",         # IT
    "INFY.NS",        # IT
    "RELIANCE.NS",    # Conglomerate
    "HINDUNILVR.NS",  # FMCG
    "ITC.NS",         # FMCG
    "MARUTI.NS",      # Auto
    "AXISBANK.NS",    # Banking
    "SBIN.NS",        # PSU Banking
    "WIPRO.NS",       # IT
    "BHARTIARTL.NS",  # Telecom
]

# Quick test set for fast validation (3-5 stocks)
QUICK_TEST_SET = [
    "HDFCBANK.NS",
    "TCS.NS",
    "RELIANCE.NS",
]

# Comprehensive test set (all tickers)
COMPREHENSIVE_TEST_SET = list(TICKER_TO_SCREENER_ID.keys())


def get_screener_id(ticker: str) -> str:
    """Get Screener.in company ID for a ticker"""
    return TICKER_TO_SCREENER_ID.get(ticker, "")


def get_all_tickers() -> List[str]:
    """Get all test tickers"""
    return list(TICKER_TO_SCREENER_ID.keys())


def get_ticker_info(ticker: str) -> Dict[str, str]:
    """Get ticker information"""
    for category, stocks in TEST_TICKERS.items():
        for stock in stocks:
            if stock["ticker"] == ticker:
                return stock
    return {}


