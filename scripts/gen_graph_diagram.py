from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

MERMAID = """
graph TD
    Start[StartNode] --> DataCollection
    DataCollection --> Technicals
    DataCollection --> Fundamentals
    DataCollection --> NewsSentiment
    DataCollection --> YouTube
    Technicals --> Cashflow
    Fundamentals --> Cashflow
    NewsSentiment --> Cashflow
    YouTube --> Cashflow
    Cashflow --> Leadership
    Leadership --> SectorMacro
    SectorMacro --> Synthesis
"""


async def main() -> None:
    out = Path("docs/graph_diagram.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://kroki.io/mermaid/png",
            content=MERMAID.encode(),
            headers={"Content-Type": "text/plain"},
        )
        resp.raise_for_status()
        out.write_bytes(resp.content)
        print(f"Wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
