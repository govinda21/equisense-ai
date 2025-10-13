"""
Main API validation test suite
Tests API responses against ground truth data from Screener.in
"""

import pytest
import logging
from typing import Dict, Any

from tests.validation.test_data import DAILY_TEST_SET, QUICK_TEST_SET
from tests.validation.validation_rules import ValidationResult

logger = logging.getLogger(__name__)


def extract_fundamentals_from_api(response_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract fundamental metrics from API response
    
    Args:
        response_data: Full API response
        
    Returns:
        Dictionary with extracted metrics
    """
    try:
        reports = response_data.get("reports", [])
        if not reports:
            logger.warning("No reports in API response")
            return {}
        
        report = reports[0]  # First ticker
        
        # Extract from fundamentals section
        fundamentals = report.get("fundamentals", {})
        comprehensive = report.get("comprehensive_fundamentals", {})
        
        extracted = {}
        
        # Market data
        extracted["current_price"] = fundamentals.get("current_price")
        extracted["market_cap"] = fundamentals.get("market_cap")
        
        # Ratios
        extracted["pe_ratio"] = fundamentals.get("pe_ratio")
        extracted["pb_ratio"] = fundamentals.get("pb_ratio")
        extracted["debt_to_equity"] = fundamentals.get("debt_to_equity")
        
        # Profitability
        extracted["roe"] = fundamentals.get("roe")
        extracted["roce"] = fundamentals.get("roce")
        extracted["roic"] = fundamentals.get("roic")
        
        # Margins
        extracted["operating_margin"] = fundamentals.get("operating_margin")
        extracted["net_margin"] = fundamentals.get("net_margin")
        extracted["ebitda_margin"] = fundamentals.get("ebitda_margin")
        
        # Coverage
        extracted["interest_coverage"] = fundamentals.get("interest_coverage")
        
        # Financials
        extracted["revenue"] = fundamentals.get("revenue")
        extracted["net_profit"] = fundamentals.get("net_profit")
        extracted["ebitda"] = fundamentals.get("ebitda")
        
        # Balance sheet
        extracted["total_debt"] = fundamentals.get("total_debt")
        extracted["equity"] = fundamentals.get("equity")
        
        # Cash flow
        extracted["fcf_yield"] = fundamentals.get("fcf_yield")
        extracted["operating_cash_flow"] = fundamentals.get("operating_cash_flow")
        
        logger.info(f"Extracted {len([v for v in extracted.values() if v is not None])} fields from API")
        return extracted
        
    except Exception as e:
        logger.error(f"Error extracting fundamentals from API: {e}")
        return {}


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", QUICK_TEST_SET)
async def test_fundamentals_accuracy(
    ticker,
    api_client,
    screener_scraper,
    validation_engine,
    test_results_storage
):
    """
    Validate fundamentals data against Screener.in
    
    This test:
    1. Fires API request for the ticker
    2. Scrapes ground truth from Screener.in
    3. Validates each field within tolerance
    4. Fails if any critical field exceeds tolerance
    """
    logger.info(f"Testing fundamentals accuracy for {ticker}")
    
    # Step 1: Fire API request
    logger.info(f"Calling API for {ticker}")
    response = await api_client.post("/analyze", json={
        "tickers": [ticker],
        "currency": "INR",
        "market": "IN"
    })
    
    assert response.status_code == 200, f"API request failed with status {response.status_code}"
    api_response = response.json()
    
    # Step 2: Extract fundamentals from API response
    api_data = extract_fundamentals_from_api(api_response)
    assert api_data, f"Failed to extract fundamentals from API response for {ticker}"
    
    # Step 3: Scrape ground truth from Screener.in
    logger.info(f"Scraping ground truth for {ticker}")
    ground_truth = await screener_scraper.get_company_data(ticker)
    assert ground_truth, f"Failed to scrape ground truth for {ticker}"
    
    # Step 4: Validate all fields
    logger.info(f"Validating {ticker} data")
    results = validation_engine.validate_all_fields(ticker, api_data, ground_truth)
    
    # Store results for report generation
    test_results_storage["results"].extend(results)
    
    # Step 5: Check for critical failures
    critical_failures = [r for r in results if not r.passed and r.critical]
    
    if critical_failures:
        failure_msg = f"Critical validation failures for {ticker}:\n"
        for r in critical_failures:
            failure_msg += f"  - {r.field}: API={r.api_value}, Truth={r.ground_truth}, Diff={r.diff_pct:.2f}%\n"
        logger.error(failure_msg)
        pytest.fail(failure_msg)
    
    # Step 6: Log warnings for non-critical mismatches
    warnings = [r for r in results if not r.passed and not r.critical]
    if warnings:
        for r in warnings:
            logger.warning(
                f"{ticker}: {r.field} mismatch - "
                f"API: {r.api_value}, Truth: {r.ground_truth}, Diff: {r.diff_pct:.2f}%"
            )
    
    # Step 7: Log success summary
    summary = validation_engine.get_summary_stats(results)
    logger.info(
        f"{ticker} validation complete: "
        f"{summary['passed']}/{summary['total_fields']} passed ({summary['pass_rate']:.1f}%), "
        f"{summary['critical_failures']} critical failures"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", QUICK_TEST_SET)
async def test_debt_equity_calculation(
    ticker,
    api_client,
    screener_scraper,
    validation_engine
):
    """
    Specific test for D/E ratio calculation (known issue area)
    Extra scrutiny on D/E as it was previously buggy for banks
    """
    logger.info(f"Testing D/E ratio calculation for {ticker}")
    
    # Fire API request
    response = await api_client.post("/analyze", json={
        "tickers": [ticker],
        "currency": "INR",
        "market": "IN"
    })
    
    assert response.status_code == 200
    api_response = response.json()
    api_data = extract_fundamentals_from_api(api_response)
    
    # Get ground truth
    ground_truth = await screener_scraper.get_company_data(ticker)
    
    # Validate D/E specifically
    api_de = api_data.get("debt_to_equity")
    gt_de = ground_truth.get("debt_to_equity")
    
    # D/E should not be None for most companies
    if gt_de is not None:
        assert api_de is not None, f"D/E ratio is None in API for {ticker} but exists in ground truth"
    
    # If both exist, validate
    if api_de is not None and gt_de is not None:
        result = validation_engine.validate_numeric(ticker, "debt_to_equity", api_de, gt_de)
        
        if not result.passed:
            logger.error(
                f"D/E validation failed for {ticker}: "
                f"API={api_de}, Truth={gt_de}, Diff={result.diff_pct:.2f}%"
            )
            pytest.fail(result.message)
        else:
            logger.info(f"D/E validation passed for {ticker}: API={api_de}, Truth={gt_de}")


@pytest.mark.asyncio
async def test_api_health(api_client):
    """Test that API is responsive"""
    response = await api_client.get("/health")
    assert response.status_code == 200
    logger.info("API health check passed")


@pytest.mark.asyncio  
async def test_screener_scraper(screener_scraper):
    """Test that Screener scraper is working"""
    data = await screener_scraper.get_company_data("HDFCBANK.NS")
    assert data, "Screener scraper returned no data"
    assert "market_cap" in data or "current_price" in data, "Screener scraper returned incomplete data"
    logger.info(f"Screener scraper test passed: extracted {len(data)} fields")


# Fixture to generate report after all tests
@pytest.fixture(scope="session", autouse=True)
def generate_reports(request, test_results_storage):
    """Generate HTML and CSV reports after all tests complete"""
    yield
    
    # This runs after all tests
    results = test_results_storage["results"]
    if results:
        from tests.validation.reporter import ValidationReporter
        from pathlib import Path
        
        reporter = ValidationReporter(output_dir=Path("tests/validation/reports"))
        reporter.generate_html_report(results)
        reporter.generate_csv_report(results)
        reporter.generate_json_report(results)
        
        logger.info(f"Generated validation reports with {len(results)} results")


