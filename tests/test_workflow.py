from __future__ import annotations

import pytest

from app.config import get_settings
from app.graph.workflow import build_research_graph


@pytest.mark.asyncio
async def test_workflow_runs_minimal():
    settings = get_settings()
    graph = build_research_graph(settings)
    out = await graph.ainvoke({"tickers": ["AAPL"]})
    assert "final_output" in out
    assert out["final_output"]["tickers"] == ["AAPL"]
