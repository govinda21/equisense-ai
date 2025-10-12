from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_research_endpoint_smoke():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/research", json={"tickers": ["AAPL"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "tickers" in data and data["tickers"] == ["AAPL"]
        assert "reports" in data and len(data["reports"]) >= 1
