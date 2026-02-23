from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class StockExchange:
    name: str
    suffix: str
    currency: str
    country: str
    timezone: str


EXCHANGES = {
    "US":  StockExchange("NASDAQ/NYSE", "",    "USD", "United States",  "America/New_York"),
    "NSE": StockExchange("National Stock Exchange of India", ".NS", "INR", "India", "Asia/Kolkata"),
    "BSE": StockExchange("Bombay Stock Exchange", ".BO", "INR", "India", "Asia/Kolkata"),
    "LSE": StockExchange("London Stock Exchange", ".L",  "GBP", "United Kingdom", "Europe/London"),
    "TSE": StockExchange("Tokyo Stock Exchange", ".T",   "JPY", "Japan",          "Asia/Tokyo"),
    "TSX": StockExchange("Toronto Stock Exchange", ".TO","CAD", "Canada",         "America/Toronto"),
    "ASX": StockExchange("Australian Securities Exchange", ".AX", "AUD", "Australia", "Australia/Sydney"),
    "FRA": StockExchange("Frankfurt Stock Exchange", ".F", "EUR", "Germany",      "Europe/Berlin"),
}

INDIAN_STOCK_MAPPING = {
    # Financial Services
    "jiofin": "JIOFIN", "jio financial": "JIOFIN",
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK",
    "icici bank": "ICICIBANK", "icicibank": "ICICIBANK",
    "sbi": "SBIN", "state bank": "SBIN",
    "axis bank": "AXISBANK", "axisbank": "AXISBANK",
    "kotak bank": "KOTAKBANK", "kotakbank": "KOTAKBANK",
    # Technology
    "tcs": "TCS", "tata consultancy": "TCS",
    "infosys": "INFY", "wipro": "WIPRO",
    "hcl tech": "HCLTECH", "hcltech": "HCLTECH",
    "tech mahindra": "TECHM", "techm": "TECHM",
    # Telecom
    "reliance": "RELIANCE", "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL", "jio": "RJIO",
    # FMCG
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR",
    "itc": "ITC", "nestle india": "NESTLEIND", "britannia": "BRITANNIA",
    # Automotive
    "maruti suzuki": "MARUTI", "maruti": "MARUTI",
    "tata motors": "TATAMOTORS", "mahindra": "M&M",
    "bajaj auto": "BAJAJ-AUTO",
    # Pharma
    "sun pharma": "SUNPHARMA", "dr reddy": "DRREDDY",
    "cipla": "CIPLA", "divi's lab": "DIVISLAB", "biocon": "BIOCON",
    # Metals
    "tata steel": "TATASTEEL", "jsl": "JINDALSTEL",
    "hindalco": "HINDALCO", "vedanta": "VEDL",
    # Oil & Gas
    "ongc": "ONGC", "ioc": "IOC", "bpcl": "BPCL", "hpcl": "HINDPETRO",
    # Retail
    "dmart": "DMART", "avenue supermarts": "DMART", "trent": "TRENT",
    # Infrastructure
    "l&t": "LT", "larsen toubro": "LT",
    "ultratech": "ULTRACEMCO", "grasim": "GRASIM",
    # Power & Energy
    "ntpc": "NTPC", "power grid": "POWERGRID",
    "adani green": "ADANIGREEN", "adani power": "ADANIPOWER",
    # Conglomerates
    "adani enterprises": "ADANIENT", "adani ports": "ADANIPORTS",
    "tata power": "TATAPOWER", "godrej": "GODREJCP",
}

US_STOCK_MAPPING = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA", "meta": "META", "facebook": "META",
    "nvidia": "NVDA", "netflix": "NFLX", "walmart": "WMT", "disney": "DIS",
    "coca cola": "KO", "pepsi": "PEP", "johnson & johnson": "JNJ",
    "jpmorgan": "JPM", "visa": "V", "mastercard": "MA", "boeing": "BA",
    "intel": "INTC", "cisco": "CSCO", "oracle": "ORCL",
    "salesforce": "CRM", "adobe": "ADBE", "uber": "UBER", "airbnb": "ABNB",
    "zoom": "ZM", "spotify": "SPOT", "twitter": "TWTR", "snapchat": "SNAP",
}

_CURRENCY_SYMBOLS = {"USD": "$", "INR": "₹", "GBP": "£", "EUR": "€",
                     "JPY": "¥", "CAD": "C$", "AUD": "A$"}


def normalize_ticker_input(ticker: str) -> str:
    return ticker.strip().lower()


def get_country_exchanges() -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for code, ex in EXCHANGES.items():
        result.setdefault(ex.country, []).append(code)
    return result


def map_ticker_to_symbol(ticker: str, country: str = "United States") -> Tuple[str, str, str]:
    """Map ticker input to (yahoo_symbol, exchange_code, currency)."""
    normalized = normalize_ticker_input(ticker)
    upper = ticker.upper()

    # Already has suffix
    for code, ex in EXCHANGES.items():
        if ex.suffix and upper.endswith(ex.suffix):
            return upper, code, ex.currency

    if country == "India":
        if normalized in INDIAN_STOCK_MAPPING:
            return f"{INDIAN_STOCK_MAPPING[normalized]}.NS", "NSE", "INR"
        sym = upper if upper.endswith((".NS", ".BO")) else upper + ".NS"
        return sym, "NSE", "INR"

    if country == "United States":
        if normalized in US_STOCK_MAPPING:
            return US_STOCK_MAPPING[normalized], "US", "USD"
        return upper, "US", "USD"

    for code, ex in EXCHANGES.items():
        if ex.country == country:
            sym = upper if (not ex.suffix or upper.endswith(ex.suffix)) else upper + ex.suffix
            return sym, code, ex.currency

    return upper + ".NS", "NSE", "INR"


def get_currency_symbol(currency: str) -> str:
    return _CURRENCY_SYMBOLS.get(currency, currency)


def format_market_cap(value: float, currency: str) -> str:
    sym = get_currency_symbol(currency)
    if currency == "INR":
        if value >= 1e7: return f"{sym}{value/1e7:.1f} Cr"
        if value >= 1e5: return f"{sym}{value/1e5:.1f} L"
        return f"{sym}{value:,.0f}"
    if value >= 1e12: return f"{sym}{value/1e12:.1f}T"
    if value >= 1e9:  return f"{sym}{value/1e9:.1f}B"
    if value >= 1e6:  return f"{sym}{value/1e6:.1f}M"
    return f"{sym}{value:,.0f}"


def detect_country_from_ticker(ticker: str) -> str:
    upper = ticker.upper()
    for ex in EXCHANGES.values():
        if ex.suffix and upper.endswith(ex.suffix):
            return ex.country
    if normalize_ticker_input(ticker) in INDIAN_STOCK_MAPPING:
        return "India"
    return "India"


def get_supported_countries() -> List[str]:
    return sorted({ex.country for ex in EXCHANGES.values()})


def validate_ticker_format(ticker: str, country: str) -> bool:
    try:
        return bool(map_ticker_to_symbol(ticker, country)[0])
    except Exception:
        return False


if __name__ == "__main__":
    for ticker, country in [("jiofin", "India"), ("BAJFINANCE", "India"),
                             ("apple", "United States"), ("AAPL", "United States"),
                             ("RELIANCE.NS", "India")]:
        sym, ex, cur = map_ticker_to_symbol(ticker, country)
        print(f"{ticker} ({country}) -> {sym} [{ex}] {cur}")
