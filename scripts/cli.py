from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.config import get_settings
from app.graph.workflow import build_research_graph


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run agentic stock research")
    parser.add_argument("--tickers", nargs="+", required=True, help="Tickers, e.g., AAPL MSFT")
    parser.add_argument("--out", type=str, default="report.json", help="Output JSON path")
    args = parser.parse_args()

    settings = get_settings()
    graph = build_research_graph(settings)
    result = await graph.ainvoke({"tickers": args.tickers})
    out_path = Path(args.out)
    out_path.write_text(json.dumps(result["final_output"], indent=2))
    print(f"Saved {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
