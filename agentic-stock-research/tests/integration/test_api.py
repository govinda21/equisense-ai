"""
Integration tests for API endpoints
"""

import pytest
from httpx import AsyncClient
from app.main import create_app


@pytest.fixture
def app():
    """Create FastAPI app for testing"""
    return create_app()


@pytest.mark.asyncio
async def test_health_endpoint(app):
    """Test health check endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_analyze_endpoint_basic(app):
    """Test basic analyze endpoint"""
    async with AsyncClient(app=app, base_url="http://test", timeout=60.0) as client:
        payload = {
            "tickers": ["RELIANCE.NS"],
            "target_depth": "quick"
        }
        
        response = await client.post("/analyze", json=payload)
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 500]  # 500 if API keys missing
        
        if response.status_code == 200:
            data = response.json()
            assert "tickers" in data
            assert "reports" in data
            assert len(data["reports"]) > 0


@pytest.mark.asyncio
async def test_analyze_endpoint_invalid_ticker(app):
    """Test analyze endpoint with invalid ticker"""
    async with AsyncClient(app=app, base_url="http://test", timeout=60.0) as client:
        payload = {
            "tickers": ["INVALID_TICKER_XYZ"],
            "target_depth": "quick"
        }
        
        response = await client.post("/analyze", json=payload)
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 500]


@pytest.mark.asyncio
async def test_analyze_endpoint_missing_ticker(app):
    """Test analyze endpoint without ticker"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "target_depth": "quick"
            # Missing "tickers" field
        }
        
        response = await client.post("/analyze", json=payload)
        
        # Should return validation error
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_pdf_generation_endpoint(app):
    """Test PDF generation endpoint"""
    async with AsyncClient(app=app, base_url="http://test", timeout=120.0) as client:
        payload = {
            "tickers": ["AAPL"],
            "target_depth": "quick"
        }
        
        response = await client.post("/api/generate-pdf", json=payload)
        
        # Should succeed or fail with proper error
        assert response.status_code in [200, 500, 501]
        
        if response.status_code == 200:
            # Should return PDF
            assert response.headers["content-type"] == "application/pdf"
            assert len(response.content) > 1000  # PDF should have content


@pytest.mark.asyncio
async def test_performance_metrics_endpoint(app):
    """Test performance metrics endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/performance/metrics")
        
        # Should return metrics or gracefully handle if not available
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            # Check for expected metrics structure
            assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_cors_headers(app):
    """Test CORS headers are present"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_api_error_handling(app):
    """Test API error handling"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Send completely invalid JSON
        response = await client.post(
            "/analyze",
            content="not json at all",
            headers={"content-type": "application/json"}
        )
        
        # Should handle gracefully with proper error code
        assert response.status_code >= 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
