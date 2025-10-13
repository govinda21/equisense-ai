"""
Pytest fixtures for validation tests
"""

import pytest
import httpx
import logging
from pathlib import Path

from tests.validation.ground_truth_scraper import ScreenerScraper
from tests.validation.validation_rules import ValidationEngine
from tests.validation.reporter import ValidationReporter

logging.basicConfig(level=logging.INFO)


@pytest.fixture
async def api_client():
    """HTTP client for API requests"""
    async with httpx.AsyncClient(
        base_url="http://localhost:8000",
        timeout=60.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def screener_scraper():
    """Screener.in scraper with caching"""
    scraper = ScreenerScraper(
        cache_dir="tests/validation/.cache",
        cache_ttl_hours=24
    )
    await scraper.start()
    yield scraper
    await scraper.close()


@pytest.fixture
def validation_engine():
    """Validation engine with rules"""
    return ValidationEngine()


@pytest.fixture
def validation_reporter():
    """HTML and CSV report generator"""
    output_dir = Path("tests/validation/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    return ValidationReporter(output_dir=output_dir)


@pytest.fixture(scope="session")
def test_results_storage():
    """Storage for accumulating test results across all tests"""
    return {"results": []}


