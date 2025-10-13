#!/usr/bin/env python3
"""
CLI script for running API validation manually
Usage: python run_validation.py [--quick|--full|--ticker TICKER]
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.validation.ground_truth_scraper import ScreenerScraper
from tests.validation.validation_rules import ValidationEngine
from tests.validation.reporter import ValidationReporter
from tests.validation.test_data import QUICK_TEST_SET, DAILY_TEST_SET

import httpx

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def validate_ticker(ticker: str, api_client: httpx.AsyncClient, scraper: ScreenerScraper, engine: ValidationEngine):
    """Validate a single ticker"""
    logger.info(f"Validating {ticker}...")
    
    try:
        # Fire API request
        response = await api_client.post("/analyze", json={
            "tickers": [ticker],
            "currency": "INR",
            "market": "IN"
        })
        
        if response.status_code != 200:
            logger.error(f"API request failed for {ticker}: {response.status_code}")
            return []
        
        api_response = response.json()
        
        # Extract fundamentals
        reports = api_response.get("reports", [])
        if not reports:
            logger.error(f"No reports in API response for {ticker}")
            return []
        
        report = reports[0]
        fundamentals = report.get("fundamentals", {})
        
        api_data = {
            "current_price": fundamentals.get("current_price"),
            "market_cap": fundamentals.get("market_cap"),
            "pe_ratio": fundamentals.get("pe_ratio"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "roe": fundamentals.get("roe"),
            "revenue": fundamentals.get("revenue"),
        }
        
        # Get ground truth
        ground_truth = await scraper.get_company_data(ticker)
        
        if not ground_truth:
            logger.error(f"Failed to scrape ground truth for {ticker}")
            return []
        
        # Validate
        results = engine.validate_all_fields(ticker, api_data, ground_truth)
        
        # Log summary
        summary = engine.get_summary_stats(results)
        logger.info(
            f"{ticker}: {summary['passed']}/{summary['total_fields']} passed "
            f"({summary['pass_rate']:.1f}%), {summary['critical_failures']} critical failures"
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error validating {ticker}: {e}")
        return []


async def main():
    parser = argparse.ArgumentParser(description="Run API validation tests")
    parser.add_argument("--quick", action="store_true", help="Run quick test (3 stocks)")
    parser.add_argument("--full", action="store_true", help="Run full daily test (12 stocks)")
    parser.add_argument("--ticker", type=str, help="Test specific ticker (e.g., HDFCBANK.NS)")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000", help="API base URL")
    
    args = parser.parse_args()
    
    # Determine which tickers to test
    if args.ticker:
        tickers = [args.ticker]
    elif args.full:
        tickers = DAILY_TEST_SET
    else:  # Default to quick
        tickers = QUICK_TEST_SET
    
    logger.info(f"Testing {len(tickers)} tickers: {', '.join(tickers)}")
    
    # Initialize components
    async with httpx.AsyncClient(base_url=args.api_url, timeout=60.0) as api_client:
        async with ScreenerScraper() as scraper:
            engine = ValidationEngine()
            
            # Test API health
            try:
                health = await api_client.get("/health")
                if health.status_code != 200:
                    logger.error("API health check failed")
                    return 1
                logger.info("✅ API is healthy")
            except Exception as e:
                logger.error(f"Failed to connect to API: {e}")
                return 1
            
            # Run validation for each ticker
            all_results = []
            for ticker in tickers:
                results = await validate_ticker(ticker, api_client, scraper, engine)
                all_results.extend(results)
            
            # Generate reports
            if all_results:
                reporter = ValidationReporter(output_dir=Path("tests/validation/reports"))
                reporter.generate_html_report(all_results)
                reporter.generate_csv_report(all_results)
                reporter.generate_json_report(all_results)
                
                # Print summary
                overall_summary = engine.get_summary_stats(all_results)
                print("\n" + "="*60)
                print("VALIDATION SUMMARY")
                print("="*60)
                print(f"Total Fields Tested: {overall_summary['total_fields']}")
                print(f"Passed: {overall_summary['passed']}")
                print(f"Failed: {overall_summary['failed']}")
                print(f"Critical Failures: {overall_summary['critical_failures']}")
                print(f"Pass Rate: {overall_summary['pass_rate']:.1f}%")
                print("="*60)
                
                # Exit with error code if critical failures
                if overall_summary['critical_failures'] > 0:
                    logger.error("❌ Validation failed with critical errors")
                    return 1
                else:
                    logger.info("✅ Validation passed")
                    return 0
            else:
                logger.error("No validation results generated")
                return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


