from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class StockExchange:
    name: str
    suffix: str
    currency: str
    country: str
    timezone: str


# Exchange definitions
EXCHANGES = {
    "US": StockExchange("NASDAQ/NYSE", "", "USD", "United States", "America/New_York"),
    "NSE": StockExchange("National Stock Exchange of India", ".NS", "INR", "India", "Asia/Kolkata"),
    "BSE": StockExchange("Bombay Stock Exchange", ".BO", "INR", "India", "Asia/Kolkata"),
    "LSE": StockExchange("London Stock Exchange", ".L", "GBP", "United Kingdom", "Europe/London"),
    "TSE": StockExchange("Tokyo Stock Exchange", ".T", "JPY", "Japan", "Asia/Tokyo"),
    "TSX": StockExchange("Toronto Stock Exchange", ".TO", "CAD", "Canada", "America/Toronto"),
    "ASX": StockExchange("Australian Securities Exchange", ".AX", "AUD", "Australia", "Australia/Sydney"),
    "FRA": StockExchange("Frankfurt Stock Exchange", ".F", "EUR", "Germany", "Europe/Berlin"),
}

# Indian stock symbol mappings (common name -> NSE symbol)
INDIAN_STOCK_MAPPING = {
    # Financial Services
    "jiofin": "JIOFIN",
    "jio financial": "JIOFIN",
    "bajaj finance": "BAJFINANCE",
    "bajfinance": "BAJFINANCE",
    "hdfc bank": "HDFCBANK",
    "hdfcbank": "HDFCBANK",
    "icici bank": "ICICIBANK",
    "icicibank": "ICICIBANK",
    "sbi": "SBIN",
    "state bank": "SBIN",
    "axis bank": "AXISBANK",
    "axisbank": "AXISBANK",
    "kotak bank": "KOTAKBANK",
    "kotakbank": "KOTAKBANK",
    
    # Technology
    "tcs": "TCS",
    "tata consultancy": "TCS",
    "infosys": "INFY",
    "wipro": "WIPRO",
    "hcl tech": "HCLTECH",
    "hcltech": "HCLTECH",
    "tech mahindra": "TECHM",
    "techm": "TECHM",
    
    # Telecom
    "reliance": "RELIANCE",
    "bharti airtel": "BHARTIARTL",
    "airtel": "BHARTIARTL",
    "jio": "RJIO",  # Note: RIL owns Jio
    
    # FMCG
    "hindustan unilever": "HINDUNILVR",
    "hul": "HINDUNILVR",
    "itc": "ITC",
    "nestle india": "NESTLEIND",
    "britannia": "BRITANNIA",
    
    # Automotive
    "maruti suzuki": "MARUTI",
    "maruti": "MARUTI",
    "tata motors": "TATAMOTORS",
    "mahindra": "M&M",
    "bajaj auto": "BAJAJ-AUTO",
    
    # Pharma
    "sun pharma": "SUNPHARMA",
    "dr reddy": "DRREDDY",
    "cipla": "CIPLA",
    "divi's lab": "DIVISLAB",
    "biocon": "BIOCON",
    
    # Metals & Mining
    "tata steel": "TATASTEEL",
    "jsl": "JINDALSTEL",
    "hindalco": "HINDALCO",
    "vedanta": "VEDL",
    
    # Oil & Gas
    "ongc": "ONGC",
    "ioc": "IOC",
    "bpcl": "BPCL",
    "hpcl": "HINDPETRO",
    
    # Retail
    "dmart": "DMART",
    "avenue supermarts": "DMART",
    "trent": "TRENT",
    
    # Infrastructure
    "l&t": "LT",
    "larsen toubro": "LT",
    "ultratech": "ULTRACEMCO",
    "grasim": "GRASIM",
    
    # Power & Energy
    "ntpc": "NTPC",
    "power grid": "POWERGRID",
    "adani green": "ADANIGREEN",
    "adani power": "ADANIPOWER",
    
    # Conglomerates
    "adani enterprises": "ADANIENT",
    "adani ports": "ADANIPORTS",
    "tata power": "TATAPOWER",
    "godrej": "GODREJCP",
}

# US stock mappings (common name -> symbol)
US_STOCK_MAPPING = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "walmart": "WMT",
    "disney": "DIS",
    "coca cola": "KO",
    "pepsi": "PEP",
    "johnson & johnson": "JNJ",
    "jpmorgan": "JPM",
    "visa": "V",
    "mastercard": "MA",
    "boeing": "BA",
    "intel": "INTC",
    "cisco": "CSCO",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "uber": "UBER",
    "airbnb": "ABNB",
    "zoom": "ZM",
    "spotify": "SPOT",
    "twitter": "TWTR",
    "snapchat": "SNAP",
    "linkedin": "LNKD",
}


def normalize_ticker_input(ticker: str) -> str:
    """Normalize ticker input by removing extra spaces and converting to lowercase"""
    return ticker.strip().lower()


def get_country_exchanges() -> Dict[str, List[str]]:
    """Get mapping of countries to their stock exchanges"""
    country_exchanges = {}
    for exchange_code, exchange in EXCHANGES.items():
        country = exchange.country
        if country not in country_exchanges:
            country_exchanges[country] = []
        country_exchanges[country].append(exchange_code)
    return country_exchanges


def map_ticker_to_symbol(ticker: str, country: str = "United States") -> Tuple[str, str, str]:
    """
    Map a ticker input to the correct Yahoo Finance symbol
    
    Args:
        ticker: User input ticker (e.g., "jiofin", "BAJFINANCE", "apple")
        country: Target country for the stock
        
    Returns:
        Tuple of (mapped_symbol, exchange_code, currency)
    """
    normalized_ticker = normalize_ticker_input(ticker)
    
    # If already has exchange suffix, return as-is
    if any(ticker.upper().endswith(ex.suffix) for ex in EXCHANGES.values() if ex.suffix):
        for ex_code, ex in EXCHANGES.items():
            if ticker.upper().endswith(ex.suffix):
                return ticker.upper(), ex_code, ex.currency
    
    # Country-specific mapping
    if country == "India":
        # Check Indian stock mapping first
        if normalized_ticker in INDIAN_STOCK_MAPPING:
            symbol = INDIAN_STOCK_MAPPING[normalized_ticker]
            # Default to NSE unless already specified
            return f"{symbol}.NS", "NSE", "INR"
        
        # If no mapping found, assume it's already a valid NSE symbol
        symbol = ticker.upper()
        if not symbol.endswith(('.NS', '.BO')):
            symbol += '.NS'  # Default to NSE
        return symbol, "NSE", "INR"
    
    elif country == "United States":
        # Check US stock mapping
        if normalized_ticker in US_STOCK_MAPPING:
            symbol = US_STOCK_MAPPING[normalized_ticker]
            return symbol, "US", "USD"
        
        # Assume it's already a valid US symbol
        return ticker.upper(), "US", "USD"
    
    # For other countries, return as-is with appropriate suffix
    for ex_code, ex in EXCHANGES.items():
        if ex.country == country:
            symbol = ticker.upper()
            if ex.suffix and not symbol.endswith(ex.suffix):
                symbol += ex.suffix
            return symbol, ex_code, ex.currency
    
    # Default to US market
    return ticker.upper(), "US", "USD"


def get_currency_symbol(currency: str) -> str:
    """Get currency symbol for display"""
    symbols = {
        "USD": "$",
        "INR": "₹", 
        "GBP": "£",
        "EUR": "€",
        "JPY": "¥",
        "CAD": "C$",
        "AUD": "A$",
    }
    return symbols.get(currency, currency)


def format_market_cap(value: float, currency: str) -> str:
    """Format market cap based on currency"""
    if currency == "INR":
        # Indian format: use Crores and Lakhs
        if value >= 1e9:
            return f"₹{value/1e7:.1f} Cr"
        elif value >= 1e7:
            return f"₹{value/1e7:.2f} Cr"
        elif value >= 1e5:
            return f"₹{value/1e5:.1f} L"
        else:
            return f"₹{value:,.0f}"
    else:
        # International format: use Billions, Millions
        if value >= 1e12:
            return f"{get_currency_symbol(currency)}{value/1e12:.1f}T"
        elif value >= 1e9:
            return f"{get_currency_symbol(currency)}{value/1e9:.1f}B"
        elif value >= 1e6:
            return f"{get_currency_symbol(currency)}{value/1e6:.1f}M"
        else:
            return f"{get_currency_symbol(currency)}{value:,.0f}"


def detect_country_from_ticker(ticker: str) -> str:
    """Detect country from ticker format"""
    ticker_upper = ticker.upper()
    
    for exchange_code, exchange in EXCHANGES.items():
        if exchange.suffix and ticker_upper.endswith(exchange.suffix):
            return exchange.country
    
    # Check if it's a known Indian stock
    normalized = normalize_ticker_input(ticker)
    if normalized in INDIAN_STOCK_MAPPING:
        return "India"
    
    # Default to US
    return "United States"


def get_supported_countries() -> List[str]:
    """Get list of supported countries"""
    countries = set()
    for exchange in EXCHANGES.values():
        countries.add(exchange.country)
    return sorted(list(countries))


def validate_ticker_format(ticker: str, country: str) -> bool:
    """Validate if ticker format is appropriate for the country"""
    try:
        mapped_symbol, _, _ = map_ticker_to_symbol(ticker, country)
        return bool(mapped_symbol)
    except:
        return False


# Test the mapping
if __name__ == "__main__":
    # Test cases
    test_cases = [
        ("jiofin", "India"),
        ("BAJFINANCE", "India"), 
        ("apple", "United States"),
        ("AAPL", "United States"),
        ("RELIANCE.NS", "India"),
    ]
    
    for ticker, country in test_cases:
        symbol, exchange, currency = map_ticker_to_symbol(ticker, country)
        print(f"{ticker} ({country}) -> {symbol} [{exchange}] {currency}")
