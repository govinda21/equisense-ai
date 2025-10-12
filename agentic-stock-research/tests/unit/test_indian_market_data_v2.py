"""
Unit tests for Indian Market Data Federation System (v2)

Tests the multi-source data federation, reconciliation, and quality scoring.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.tools.indian_market_data_v2 import (
    DataSourceType,
    DataQuality,
    DataSourceResult,
    ReconciledData,
    BSEDataSource,
    ScreenerDataSource,
    MoneyControlDataSource,
    DataReconciler,
    IndianMarketDataFederator,
    fetch_indian_market_data
)


class TestDataSourceResult:
    """Test DataSourceResult dataclass"""
    
    def test_create_success_result(self):
        result = DataSourceResult(
            source=DataSourceType.BSE,
            success=True,
            data={"symbol": "500325", "last_price": 2850.0},
            quality_score=0.9,
            fields_present=["symbol", "last_price"]
        )
        
        assert result.source == DataSourceType.BSE
        assert result.success is True
        assert result.data["last_price"] == 2850.0
        assert result.quality_score == 0.9
    
    def test_create_failure_result(self):
        result = DataSourceResult(
            source=DataSourceType.SCREENER,
            success=False,
            error="Timeout"
        )
        
        assert result.success is False
        assert result.error == "Timeout"
        assert result.data is None


class TestBSEDataSource:
    """Test BSE data source implementation"""
    
    @pytest.mark.asyncio
    async def test_fetch_without_api_key(self):
        source = BSEDataSource(api_key=None)
        result = await source.fetch_company_data("500325")
        
        assert result.success is False
        assert "API" in result.error or result.data is None
    
    @pytest.mark.asyncio
    async def test_validate_data_quality(self):
        source = BSEDataSource()
        
        # Complete data
        complete_data = {
            "symbol": "500325",
            "company_name": "Reliance Industries",
            "last_price": 2850.0,
            "market_cap": 1900000000000,
            "volume": 5000000,
            "pe_ratio": 28.5,
            "pb_ratio": 3.2,
            "dividend_yield": 0.0035
        }
        
        is_valid, quality, fields = source.validate_data(complete_data)
        
        assert is_valid is True
        assert quality > 0.8  # High quality for complete data
        assert len(fields) >= 6
    
    @pytest.mark.asyncio
    async def test_validate_data_missing_required(self):
        source = BSEDataSource()
        
        # Missing required fields
        incomplete_data = {
            "symbol": "500325"
        }
        
        is_valid, quality, fields = source.validate_data(incomplete_data)
        
        assert is_valid is False
        assert quality == 0.0
    
    def test_success_rate_tracking(self):
        source = BSEDataSource()
        
        # Simulate requests
        source.total_requests = 10
        source.success_count = 8
        source.failure_count = 2
        
        assert source.get_success_rate() == 0.8
        assert source.get_reliability_weight() == 1.0  # >80% success
    
    def test_reliability_weight_low_volume(self):
        source = BSEDataSource()
        
        # Low volume
        source.total_requests = 5
        source.success_count = 4
        
        assert source.get_reliability_weight() == 0.5  # Default for low volume


class TestScreenerDataSource:
    """Test Screener.in data source implementation"""
    
    @pytest.mark.asyncio
    async def test_parse_number(self):
        source = ScreenerDataSource()
        
        assert source._parse_number("2,850.50") == 2850.5
        assert source._parse_number("₹1,234") == 1234.0
        assert source._parse_number("invalid") == 0.0
    
    @pytest.mark.asyncio
    async def test_parse_percentage(self):
        source = ScreenerDataSource()
        
        assert source._parse_percentage("15.5%") == 0.155
        assert source._parse_percentage("5") == 0.05
        assert source._parse_percentage("invalid") == 0.0
    
    @pytest.mark.asyncio
    async def test_parse_market_cap(self):
        source = ScreenerDataSource()
        
        assert source._parse_market_cap("1,90,000 Cr") == 1900000000000.0
        assert source._parse_market_cap("50 Lakh") == 5000000.0
        assert source._parse_market_cap("100") == 100.0
    
    @pytest.mark.asyncio
    async def test_parse_screener_page_basic(self):
        source = ScreenerDataSource()
        
        # Mock HTML
        html = """
        <html>
            <h1 class="h2">Reliance Industries</h1>
            <div id="warehouse">
                <li class="flex flex-space-between">
                    <span class="name">Market Cap</span>
                    <span class="number">1,90,000 Cr</span>
                </li>
                <li class="flex flex-space-between">
                    <span class="name">Current Price</span>
                    <span class="number">2,850</span>
                </li>
                <li class="flex flex-space-between">
                    <span class="name">Stock P/E</span>
                    <span class="number">28.5</span>
                </li>
            </div>
        </html>
        """
        
        data = source._parse_screener_page(html, "RELIANCE")
        
        assert data is not None
        assert data["symbol"] == "RELIANCE"
        assert data["company_name"] == "Reliance Industries"
        assert data["market_cap"] == 1900000000000.0
        assert data["last_price"] == 2850.0
        assert data["pe_ratio"] == 28.5
    
    @pytest.mark.asyncio
    async def test_validate_data_quality(self):
        source = ScreenerDataSource()
        
        data = {
            "symbol": "RELIANCE",
            "company_name": "Reliance Industries",
            "market_cap": 1900000000000.0,
            "pe_ratio": 28.5,
            "pb_ratio": 3.2,
            "roe": 0.15,
            "roce": 0.18,
            "debt_to_equity": 0.5,
            "promoter_holding": 0.505
        }
        
        is_valid, quality, fields = source.validate_data(data)
        
        assert is_valid is True
        assert quality > 0.7  # Good quality
        assert len(fields) >= 8


class TestDataReconciler:
    """Test data reconciliation engine"""
    
    def test_reconcile_single_source(self):
        reconciler = DataReconciler()
        
        results = [
            DataSourceResult(
                source=DataSourceType.BSE,
                success=True,
                data={"symbol": "500325", "last_price": 2850.0, "market_cap": 1.9e12},
                quality_score=0.9,
                fields_present=["symbol", "last_price", "market_cap"]
            )
        ]
        
        reconciled = reconciler.reconcile("500325.BO", results)
        
        assert reconciled.ticker == "500325.BO"
        assert reconciled.data["last_price"] == 2850.0
        assert reconciled.primary_source == DataSourceType.BSE
        assert len(reconciled.sources_used) == 1
        assert len(reconciled.conflicts) == 0
    
    def test_reconcile_multiple_sources_no_conflict(self):
        reconciler = DataReconciler()
        
        results = [
            DataSourceResult(
                source=DataSourceType.BSE,
                success=True,
                data={"symbol": "500325", "last_price": 2850.0},
                quality_score=0.9,
                fields_present=["symbol", "last_price"]
            ),
            DataSourceResult(
                source=DataSourceType.SCREENER,
                success=True,
                data={"symbol": "RELIANCE", "pe_ratio": 28.5, "roe": 0.15},
                quality_score=0.8,
                fields_present=["symbol", "pe_ratio", "roe"]
            )
        ]
        
        reconciled = reconciler.reconcile("RELIANCE.NS", results)
        
        # Should have data from both sources
        assert "last_price" in reconciled.data
        assert "pe_ratio" in reconciled.data
        assert "roe" in reconciled.data
        assert len(reconciled.sources_used) == 2
        assert len(reconciled.conflicts) == 0
    
    def test_reconcile_with_conflicts(self):
        reconciler = DataReconciler()
        
        results = [
            DataSourceResult(
                source=DataSourceType.BSE,
                success=True,
                data={"symbol": "500325", "last_price": 2850.0, "pe_ratio": 28.5},
                quality_score=0.9,
                fields_present=["symbol", "last_price", "pe_ratio"]
            ),
            DataSourceResult(
                source=DataSourceType.SCREENER,
                success=True,
                data={"symbol": "RELIANCE", "last_price": 2850.0, "pe_ratio": 25.0},
                quality_score=0.7,
                fields_present=["symbol", "last_price", "pe_ratio"]
            )
        ]
        
        reconciled = reconciler.reconcile("RELIANCE.NS", results)
        
        # Should detect conflict in pe_ratio (28.5 vs 25.0 = 12.3% difference)
        assert len(reconciled.conflicts) == 1
        assert reconciled.conflicts[0]["field"] == "pe_ratio"
        assert reconciled.conflicts[0]["difference_pct"] > 0.10
    
    def test_reconcile_no_successful_sources(self):
        reconciler = DataReconciler()
        
        results = [
            DataSourceResult(
                source=DataSourceType.BSE,
                success=False,
                error="Timeout"
            ),
            DataSourceResult(
                source=DataSourceType.SCREENER,
                success=False,
                error="404 Not Found"
            )
        ]
        
        reconciled = reconciler.reconcile("UNKNOWN.NS", results)
        
        assert len(reconciled.data) == 0
        assert reconciled.quality_score == 0.0
        assert len(reconciled.sources_used) == 0
    
    def test_calculate_quality_score(self):
        reconciler = DataReconciler()
        
        # High quality, multiple sources, no conflicts
        results = [
            DataSourceResult(source=DataSourceType.BSE, success=True, data={}, quality_score=0.9, fields_present=[]),
            DataSourceResult(source=DataSourceType.SCREENER, success=True, data={}, quality_score=0.8, fields_present=[])
        ]
        conflicts = []
        
        quality = reconciler._calculate_quality_score(results, conflicts)
        
        # Average 0.85 + multi-source bonus (0.1) = 0.95
        assert quality >= 0.85
        assert quality <= 1.0
    
    def test_calculate_quality_score_with_conflicts(self):
        reconciler = DataReconciler()
        
        # High quality but many conflicts
        results = [
            DataSourceResult(source=DataSourceType.BSE, success=True, data={}, quality_score=0.9, fields_present=[])
        ]
        conflicts = [{"field": "pe"}, {"field": "pb"}, {"field": "roe"}]  # 3 conflicts
        
        quality = reconciler._calculate_quality_score(results, conflicts)
        
        # Base 0.9 - conflict penalty (0.15) = 0.75
        assert quality < 0.9


class TestIndianMarketDataFederator:
    """Test main federator class"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        federator = IndianMarketDataFederator()
        
        assert len(federator.sources) == 3
        assert isinstance(federator.sources[0], BSEDataSource)
        assert isinstance(federator.sources[1], ScreenerDataSource)
        assert isinstance(federator.sources[2], MoneyControlDataSource)
    
    @pytest.mark.asyncio
    async def test_get_company_data_all_sources_fail(self):
        federator = IndianMarketDataFederator()
        
        # Mock all sources to fail
        for source in federator.sources:
            source.fetch_company_data = AsyncMock(
                return_value=DataSourceResult(
                    source=source.__class__.__name__,
                    success=False,
                    error="Mocked failure"
                )
            )
        
        result = await federator.get_company_data("TEST.NS")
        
        assert len(result.data) == 0
        assert result.quality_score == 0.0
    
    @pytest.mark.asyncio
    async def test_get_health_status(self):
        federator = IndianMarketDataFederator()
        
        # Simulate some requests
        federator.sources[0].total_requests = 100
        federator.sources[0].success_count = 85
        federator.sources[0].failure_count = 15
        
        health = await federator.get_health_status()
        
        assert "sources" in health
        assert len(health["sources"]) == 3
        assert health["sources"][0]["success_rate"] == 0.85
        assert "timestamp" in health
    
    @pytest.mark.asyncio
    async def test_close(self):
        federator = IndianMarketDataFederator()
        
        # Should not raise any errors
        await federator.close()


class TestConvenienceFunction:
    """Test convenience wrapper function"""
    
    @pytest.mark.asyncio
    async def test_fetch_indian_market_data(self):
        # This will use actual implementations (or mocks if API keys not present)
        # Just test that it doesn't crash
        data = await fetch_indian_market_data("RELIANCE.NS")
        
        assert isinstance(data, dict)
        # Data may be empty if no API keys configured


# Integration test markers
@pytest.mark.integration
class TestIntegration:
    """Integration tests (require actual API access)"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration", default=False),
        reason="Integration tests disabled by default"
    )
    async def test_real_bse_api(self):
        """Test with real BSE API (requires API key)"""
        import os
        api_key = os.getenv("BSE_API_KEY")
        
        if not api_key:
            pytest.skip("BSE_API_KEY not configured")
        
        source = BSEDataSource(api_key=api_key)
        result = await source.fetch_company_data("500325")  # Reliance
        
        assert result.success is True
        assert "last_price" in result.data
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration", default=False),
        reason="Integration tests disabled by default"
    )
    async def test_real_screener(self):
        """Test with real Screener.in"""
        source = ScreenerDataSource()
        result = await source.fetch_company_data("RELIANCE")
        
        # May succeed or fail depending on rate limiting
        assert result is not None


# Pytest configuration hook
def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require API access"
    )

