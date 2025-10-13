"""
Pytest configuration and fixtures
"""

import pytest
import os
from pathlib import Path


@pytest.fixture
def test_ticker():
    """Test ticker symbol"""
    return "RELIANCE.NS"


@pytest.fixture
def test_ticker_us():
    """US test ticker symbol"""
    return "AAPL"


@pytest.fixture
def mock_financial_data():
    """Mock financial data for testing"""
    return {
        "marketCap": 18686991663104,
        "totalRevenue": 9765410308096,
        "beta": 0.221,
        "sharesOutstanding": 13532472634,
        "currentPrice": 1380.9,
        "trailingPE": 25.5,
        "forwardPE": 22.1,
        "debtToEquity": 45.2,
        "returnOnEquity": 0.15,
        "revenueGrowth": 0.12
    }


@pytest.fixture
def mock_comprehensive_fundamentals():
    """Mock comprehensive fundamentals data"""
    return {
        "overall_score": 63.6,
        "overall_grade": "C+",
        "recommendation": "Hold",
        "confidence_level": 0.75,
        "intrinsic_value": 714.38,
        "margin_of_safety": 0.48,
        "upside_potential": 0.48,
        "financial_health_score": 70.0,
        "valuation_score": 60.0,
        "growth_prospects_score": 65.0,
        "governance_score": 55.0,
        "macro_sensitivity_score": 68.0,
        "position_sizing_pct": 5.0,
        "entry_zone_low": 446.49,
        "entry_zone_high": 714.38,
        "target_price": 714.38,
        "stop_loss": 1173.76,
        "time_horizon_months": 12,
        "risk_rating": "Medium",
        "key_risks": ["Market volatility", "Regulatory changes", "Commodity prices"],
        "key_catalysts": ["New products", "Market expansion", "Cost optimization"],
        "key_insights": ["Strong fundamentals", "Reasonable valuation", "Growth potential"],
        "data_quality": "Good"
    }


@pytest.fixture
def mock_ticker_report():
    """Mock complete ticker report"""
    return {
        "ticker": "RELIANCE.NS",
        "executive_summary": "Strong Buy with 48% upside potential",
        "decision": {
            "action": "Hold",
            "rating": 3.2,
            "letter_grade": "C+",
            "stars": "★★★☆☆",
            "expected_return_pct": 48.26,
            "professional_rationale": "Balanced risk-reward profile",
            "top_reasons_for": ["Strong fundamentals", "Market leader"],
            "top_reasons_against": ["High valuation", "Cyclical exposure"]
        },
        "comprehensive_fundamentals": {
            "overall_score": 63.6,
            "overall_grade": "C+",
            "recommendation": "Hold",
            "confidence_level": 0.75,
            "intrinsic_value": 714.38,
            "margin_of_safety": 0.48,
            "financial_health_score": 70.0,
            "valuation_score": 60.0,
            "growth_prospects_score": 65.0,
            "governance_score": 55.0,
            "macro_sensitivity_score": 68.0,
            "entry_zone_low": 446.49,
            "entry_zone_high": 714.38,
            "target_price": 714.38,
            "stop_loss": 1173.76,
            "position_sizing_pct": 5.0,
            "time_horizon_months": 12,
            "risk_rating": "Medium",
            "key_risks": ["Market volatility"],
            "key_catalysts": ["New products"],
            "key_insights": ["Strong fundamentals"],
            "data_quality": "Good",
            "upside_potential": 0.48
        }
    }


# Configure test environment
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables"""
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "ERROR"  # Reduce logging noise in tests
    yield
    os.environ.pop("TESTING", None)

