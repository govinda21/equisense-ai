# EquiSense AI - System Architecture

This document provides visual representations of the EquiSense AI system architecture.

---

## 1. System Overview

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                        EQUISENSE AI PLATFORM                      ┃
┃                   AI-Powered Stock Research System                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

                              USER LAYER
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│   📱 Web Browser (Chrome, Firefox, Safari, Edge)                │
│                                                                   │
│   ┌───────────────┐         ┌───────────────────────────┐      │
│   │ Stock Analysis│         │    AI Financial Chat      │      │
│   │    Interface  │         │       Interface           │      │
│   └───────────────┘         └───────────────────────────┘      │
│                                                                   │
└────────────────────────────┬──────────────────────────────────┘
                             │ HTTPS/REST
                             │
                        ┌────▼────┐
                        │  NGINX  │ (Future: Load Balancer + SSL)
                        └────┬────┘
                             │
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                    PRESENTATION LAYER                            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┌─────────────────────────────────────────────────────────────────┐
│  React 19 Frontend (TypeScript + Vite)      Port: 5173          │
│  ┌──────────────┐  ┌─────────────┐  ┌────────────────────┐     │
│  │  Components  │  │   Hooks     │  │   State Mgmt       │     │
│  │  - App       │  │  - Countries│  │  - useState        │     │
│  │  - Chat      │  │  - Custom   │  │  - React Query     │     │
│  │  - Charts    │  │             │  │    (future)        │     │
│  │  - Results   │  │             │  │                    │     │
│  └──────────────┘  └─────────────┘  └────────────────────┘     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/JSON
                             │
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                    APPLICATION LAYER                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (Python 3.11+)            Port: 8000           │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     API ENDPOINTS                         │  │
│  │  POST /analyze    POST /api/chat    GET /countries       │  │
│  │  GET /health      GET /performance  GET /debug           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────┼──────────────────────────────┐    │
│  │        MIDDLEWARE         │                              │    │
│  │  CORS │ Logging │ Error Handling │ Performance Monitor  │    │
│  └──────────────────────────┼──────────────────────────────┘    │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │              LANGGRAPH ORCHESTRATION                     │    │
│  │                                                           │    │
│  │    ┌─────────┐                                          │    │
│  │    │  START  │                                          │    │
│  │    └────┬────┘                                          │    │
│  │         │                                                │    │
│  │    ┌────▼────────┐                                      │    │
│  │    │    DATA     │  (Parallel fetch OHLCV + Info)       │    │
│  │    │ COLLECTION  │                                      │    │
│  │    └─────┬───────┘                                      │    │
│  │          │                                                │    │
│  │    ┌─────┴───────────────────────┐                      │    │
│  │    │    PARALLEL ANALYSIS        │                      │    │
│  │    ▼         ▼         ▼         ▼                      │    │
│  │  ┌────┐  ┌────┐  ┌────┐  ┌────┐                        │    │
│  │  │TECH│  │FUND│  │NEWS│  │TUBE│                        │    │
│  │  └─┬──┘  └─┬──┘  └─┬──┘  └─┬──┘                        │    │
│  │    │       │       │       │                             │    │
│  │    │    ┌──▼──┐    │       │                             │    │
│  │    │    │PEER │    │       │                             │    │
│  │    │    └──┬──┘    │       │                             │    │
│  │    │    ┌──▼────┐  │       │                             │    │
│  │    │    │ANALYST│  │       │                             │    │
│  │    │    └──┬────┘  │       │                             │    │
│  │    └───────┴───────┴───────┘                             │    │
│  │            │                                               │    │
│  │       ┌────▼─────┐                                        │    │
│  │       │ CASHFLOW │                                        │    │
│  │       └────┬─────┘                                        │    │
│  │       ┌────▼──────┐                                       │    │
│  │       │LEADERSHIP │                                       │    │
│  │       └────┬──────┘                                       │    │
│  │       ┌────▼──────┐                                       │    │
│  │       │  SECTOR   │                                       │    │
│  │       │   MACRO   │                                       │    │
│  │       └────┬──────┘                                       │    │
│  │       ┌────▼──────┐                                       │    │
│  │       │  GROWTH   │                                       │    │
│  │       │ PROSPECTS │                                       │    │
│  │       └────┬──────┘                                       │    │
│  │       ┌────▼──────┐                                       │    │
│  │       │VALUATION  │                                       │    │
│  │       └────┬──────┘                                       │    │
│  │       ┌────▼──────┐                                       │    │
│  │       │SYNTHESIS  │  (LLM Decision)                      │    │
│  │       └────┬──────┘                                       │    │
│  │       ┌────▼────┐                                         │    │
│  │       │   END   │                                         │    │
│  │       └─────────┘                                         │    │
│  │                                                           │    │
│  └───────────────────────────────────────────────────────────┘  │
│                             │                                     │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │                   TOOLS LAYER                            │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │    │
│  │  │Finance│ │ NLP  │ │ News │ │YouTube│ │Ticker│ │Valuation│ │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ │    │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┏━━━━━━┷━━━━━━┓    ┏━━━━━━━━┷━━━━━━━┓   ┏━━━━━━━┷━━━━━━┓
┃  AI/ML LAYER ┃    ┃  CACHE LAYER   ┃   ┃  DATA LAYER  ┃
┗━━━━━━━━━━━━━┛    ┗━━━━━━━━━━━━━━━━┛   ┗━━━━━━━━━━━━━━┛

┌──────────────┐    ┌─────────────────┐   ┌──────────────┐
│   Ollama     │    │   Redis 7       │   │   SQLite     │
│   LLM        │    │   Cache         │   │   Database   │
│              │    │                 │   │              │
│ • Gemma3:4b  │    │ TTL Strategy:   │   │ (Minimal     │
│ • Local GPU  │    │ • OHLCV: 15m    │   │  usage)      │
│ • Port 11434 │    │ • Info: 1h      │   │              │
│ • Stream API │    │ • News: 30m     │   │ Future:      │
└──────────────┘    │ • YouTube: 2h   │   │ PostgreSQL   │
                    │                 │   └──────────────┘
┌──────────────┐    │ Port: 6379      │
│  LangChain   │    │ Persistence:    │   ┌──────────────┐
│  LangGraph   │    │ RDB/AOF options │   │  External    │
│              │    └─────────────────┘   │  APIs        │
│ • Callbacks  │                          │              │
│ • Tracing    │                          │ • Yahoo      │
└──────────────┘                          │   Finance    │
                                          │ • YouTube    │
                                          │ • News Sites │
                                          └──────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                  OBSERVABILITY LAYER                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┌────────────────┐  ┌────────────────┐  ┌──────────────────┐
│   Langfuse     │  │  Structlog     │  │  Performance     │
│   (Optional)   │  │  Logging       │  │  Monitoring      │
│                │  │                │  │                  │
│ • LLM Traces   │  │ • JSON Format  │  │ • Latency Track  │
│ • Token Usage  │  │ • Structured   │  │ • Cache Metrics  │
│ • Generations  │  │ • Context      │  │ • Error Rates    │
│ Port: 3100     │  │                │  │                  │
└────────────────┘  └────────────────┘  └──────────────────┘
```

---

## 2. LangGraph Workflow Details

### 2.1 Node Execution Flow

```
                    ╔═══════════════════════════╗
                    ║   START NODE              ║
                    ║   • Validate tickers      ║
                    ║   • Initialize state      ║
                    ╚════════════╦══════════════╝
                                 ║
                                 ▼
                    ╔═══════════════════════════╗
                    ║   DATA COLLECTION         ║
                    ║   • Parallel OHLCV fetch  ║
                    ║   • Parallel info fetch   ║
                    ║   • 5 concurrent workers  ║
                    ║   Confidence: fetches/total║
                    ╚════════════╦══════════════╝
                                 ║
                    ┌────────────╨────────────┐
                    │   PARALLEL EXECUTION    │
                    └────────────┬────────────┘
                                 │
        ╔════════════╦═══════════╩════════╦═══════════╦══════════╗
        ▼            ▼                    ▼           ▼          ▼
    ┌────────┐  ┌────────┐          ┌────────┐  ┌────────┐
    │TECHNICAL│  │ FUND   │          │  NEWS  │  │YOUTUBE │
    │ANALYSIS│  │ANALYSIS│          │SENTIMENT│ │ANALYSIS│
    └────┬───┘  └────┬───┘          └────┬───┘  └────┬───┘
         │           │                   │           │
         │      ┌────▼────┐              │           │
         │      │  PEER   │              │           │
         │      │ANALYSIS │              │           │
         │      └────┬────┘              │           │
         │      ┌────▼─────┐             │           │
         │      │ ANALYST  │             │           │
         │      │RECOMMEND │             │           │
         │      └────┬─────┘             │           │
         │           │                   │           │
         └───────────┴───────────────────┴───────────┘
                     │
                ┌────▼─────┐
                │ CASHFLOW │
                │ ANALYSIS │
                └────┬─────┘
                     │
                ┌────▼──────┐
                │LEADERSHIP │
                │   & GOV   │
                └────┬──────┘
                     │
                ┌────▼──────┐
                │  SECTOR   │
                │   MACRO   │
                └────┬──────┘
                     │
                ┌────▼──────┐
                │  GROWTH   │
                │ PROSPECTS │
                └────┬──────┘
                     │
                ┌────▼──────┐
                │ VALUATION │
                │ MODELS    │
                └────┬──────┘
                     │
                ┌────▼──────┐
                │ SYNTHESIS │
                │    LLM    │
                │  DECISION │
                └────┬──────┘
                     │
                ┌────▼─────┐
                │   END    │
                │  OUTPUT  │
                └──────────┘
```

### 2.2 Node Details with Confidence Scoring

```
╔═══════════════════════════════════════════════════════════════╗
║  NODE: DATA COLLECTION                                        ║
╠═══════════════════════════════════════════════════════════════╣
║  Input:  state["tickers"]                                     ║
║  Output: state["raw_data"]                                    ║
║          state["confidences"]["data_collection"]              ║
║                                                               ║
║  Logic:                                                       ║
║    • For each ticker in parallel (max 5 workers):            ║
║      - fetch_ohlcv(ticker, period="1y")                      ║
║      - fetch_info(ticker)                                     ║
║    • Aggregate results                                        ║
║    • Confidence = successful_fetches / total_tickers          ║
║                                                               ║
║  Cache: Check Redis first (TTL: 15m for OHLCV, 1h for info) ║
║  Retry: 3 attempts with exponential backoff                   ║
║  Timeout: 60s total                                           ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║  NODE: TECHNICAL ANALYSIS                                     ║
╠═══════════════════════════════════════════════════════════════╣
║  Input:  state["raw_data"][ticker]["ohlcv_summary"]          ║
║  Output: state["analysis"]["technicals"]                      ║
║                                                               ║
║  Calculations:                                                 ║
║    • RSI (14-period)                                          ║
║    • MACD (12, 26, 9)                                         ║
║    • Bollinger Bands (20-period, 2σ)                         ║
║    • Moving Averages (20, 50, 200 SMA)                       ║
║    • Volume Analysis                                          ║
║    • Support/Resistance Levels                                ║
║                                                               ║
║  Signal Scoring:                                              ║
║    • RSI: -1 (oversold <30) to +1 (overbought >70)          ║
║    • MACD: -1 (bearish) to +1 (bullish)                     ║
║    • MA Cross: -1 (death cross) to +1 (golden cross)        ║
║    • Aggregate: average of all signals                       ║
║                                                               ║
║  Confidence: 0.9 if data complete, 0.5 if partial            ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║  NODE: SYNTHESIS (Final Decision)                            ║
╠═══════════════════════════════════════════════════════════════╣
║  Input:  All analysis results from state["analysis"]         ║
║  Output: state["final_output"] (ResearchResponse)            ║
║                                                               ║
║  Process:                                                     ║
║    1. Calculate deterministic base score (0-1):              ║
║       • Technical (30% weight)                                ║
║       • Fundamentals (25% weight)                             ║
║       • Cashflow (20% weight)                                 ║
║       • Peer Analysis (15% weight)                            ║
║       • Analyst Consensus (10% weight)                        ║
║                                                               ║
║    2. Send comprehensive prompt to LLM (Ollama):             ║
║       "Analyze the following data for {ticker}..."            ║
║       [Include all analysis results]                          ║
║                                                               ║
║    3. Parse LLM response:                                     ║
║       • Extract score (0-1)                                   ║
║       • Extract action (Buy/Hold/Sell)                       ║
║       • Extract positives and negatives                       ║
║                                                               ║
║    4. Combine scores:                                         ║
║       • If LLM score valid: adjust base ±0.2 max             ║
║       • Otherwise: use base score                             ║
║                                                               ║
║    5. Generate final recommendation:                          ║
║       Score -> Action mapping:                                ║
║       0.75+ : Strong Buy                                      ║
║       0.65-0.75: Buy                                          ║
║       0.55-0.65: Hold                                         ║
║       0.45-0.55: Weak Hold                                    ║
║       0.35-0.45: Sell                                         ║
║       <0.35: Strong Sell                                      ║
║                                                               ║
║  Confidence: 0.9 (high confidence in combined approach)      ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 3. Data Flow Diagrams

### 3.1 Request-Response Flow

```
┌─────────┐                                              ┌─────────┐
│ Browser │                                              │ Backend │
└────┬────┘                                              └────┬────┘
     │                                                        │
     │  1. POST /analyze                                     │
     │  {tickers: ["AAPL"], country: "US"}                   │
     ├──────────────────────────────────────────────────────►│
     │                                                        │
     │                                          2. Validate  │
     │                                             Request   │
     │                                                ┌───────┤
     │                                                │ Pydantic
     │                                                └───────┤
     │                                                        │
     │                                          3. Map Tickers│
     │                                             AAPL→AAPL │
     │                                                ┌───────┤
     │                                                │Ticker
     │                                                │Mapping
     │                                                └───────┤
     │                                                        │
     │                                     4. Build Workflow │
     │                                        (LangGraph)     │
     │                                                ┌───────┤
     │                                                │Graph
     │                                                │Builder
     │                                                └───────┤
     │                                                        │
     │                                     5. Execute Nodes   │
     │                                        (Async)         │
     │           ┌────────────────────────────────────────────┤
     │           │                                            │
     │           │  START → DATA_COLLECTION (check cache)    │
     │           │            ↓                               │
     │           │  ┌─────────┴─────────┐                    │
     │           │  │ Redis Cache Hit?  │                    │
     │           │  └─────────┬─────────┘                    │
     │           │            │                               │
     │           │     YES ───┴─── NO                         │
     │           │      │           │                         │
     │           │   Return    Fetch from                     │
     │           │   Cached    Yahoo Finance                  │
     │           │      │           │                         │
     │           │      └─────┬─────┘                         │
     │           │            │                               │
     │           │    PARALLEL ANALYSIS                       │
     │           │    (Technical, Fund, etc.)                 │
     │           │            ↓                               │
     │           │    SYNTHESIS (LLM)                         │
     │           │            ↓                               │
     │           │    END (Generate Response)                 │
     │           │                                            │
     │           └────────────────────────────────────────────┤
     │                                                        │
     │                                     6. Langfuse Trace │
     │                                        (Optional)      │
     │                                                ┌───────┤
     │                                                │Langfuse
     │                                                └───────┤
     │                                                        │
     │  7. Response: ResearchResponse                        │
     │  {tickers, reports, generated_at}                     │
     │◄──────────────────────────────────────────────────────┤
     │                                                        │
     │  8. Parse & Render                                    │
     ├───►                                                    │
     │  Display in UI                                         │
     │                                                        │
```

### 3.2 Caching Strategy Flow

```
                    ┌─────────────────────┐
                    │  Request Received   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Generate Cache Key │
                    │  (ticker+params)    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Check Redis Cache  │
                    └──────────┬──────────┘
                               │
                  ┌────────────┴───────────┐
                  │                        │
            Cache Hit                  Cache Miss
                  │                        │
                  ▼                        ▼
        ┌──────────────────┐    ┌──────────────────┐
        │  Return Cached   │    │  Fetch from API  │
        │      Data        │    │  (yfinance, etc) │
        └──────────┬───────┘    └──────────┬───────┘
                   │                       │
                   │                       ▼
                   │            ┌──────────────────┐
                   │            │  Store in Cache  │
                   │            │  with TTL        │
                   │            └──────────┬───────┘
                   │                       │
                   └───────────┬───────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Return Data to     │
                    │  Caller             │
                    └─────────────────────┘

Cache TTL Strategy:
┌──────────────────┬──────────┬─────────────────────┐
│ Data Type        │ TTL      │ Rationale           │
├──────────────────┼──────────┼─────────────────────┤
│ OHLCV (1d)       │ 15 min   │ Updates once/day    │
│ Company Info     │ 1 hour   │ Rarely changes      │
│ News Sentiment   │ 30 min   │ Moderate updates    │
│ YouTube Analysis │ 2 hours  │ Low frequency       │
│ Analyst Data     │ 24 hours │ Weekly updates      │
└──────────────────┴──────────┴─────────────────────┘
```

### 3.3 Error Handling Flow

```
                    ┌─────────────────────┐
                    │  Node Execution     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Try: Execute       │
                    │  Logic              │
                    └──────────┬──────────┘
                               │
                  ┌────────────┴───────────┐
                  │                        │
              Success                   Exception
                  │                        │
                  │                        ▼
                  │            ┌──────────────────────┐
                  │            │  Circuit Breaker     │
                  │            │  Check               │
                  │            └──────────┬───────────┘
                  │                       │
                  │          ┌────────────┴──────────┐
                  │          │                       │
                  │      Open (fail fast)      Closed (retry)
                  │          │                       │
                  │          ▼                       ▼
                  │    ┌──────────┐        ┌──────────────┐
                  │    │  Log     │        │  Retry Logic │
                  │    │  Error   │        │  (exp backoff)│
                  │    └────┬─────┘        └──────┬───────┘
                  │         │                     │
                  │         │        ┌────────────┴─────────┐
                  │         │        │                      │
                  │         │    Success               Max Retries
                  │         │        │                      │
                  │         │        │                      ▼
                  │         │        │            ┌──────────────┐
                  │         │        │            │  Fallback    │
                  │         │        │            │  Data        │
                  │         │        │            └──────┬───────┘
                  │         │        │                   │
                  └─────────┴────────┴───────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Update State       │
                    │  • Set result       │
                    │  • Set confidence   │
                    │    (0.0 on error)   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Continue Workflow  │
                    │  (Graceful Degrad.) │
                    └─────────────────────┘
```

---

## 4. Deployment Architecture

### 4.1 Local Development Setup

```
┌─────────────────────────────────────────────────────────────┐
│  Development Machine (localhost)                             │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │  Frontend      │  │  Backend       │  │  Ollama      │ │
│  │  npm run dev   │  │  uvicorn       │  │  ollama serve│ │
│  │  Port: 5173    │  │  Port: 8000    │  │  Port: 11434 │ │
│  └────────────────┘  └────────────────┘  └──────────────┘ │
│                                                              │
│  ┌────────────────┐  ┌────────────────────────────────────┐│
│  │  Redis         │  │  SQLite                             ││
│  │  Port: 6379    │  │  ./app.db (file)                   ││
│  └────────────────┘  └────────────────────────────────────┘│
│                                                              │
│  Optional:                                                   │
│  ┌────────────────────────────────────────────────────────┐│
│  │  Langfuse (docker-compose.langfuse.yml)                ││
│  │  Port: 3100                                             ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Docker Compose Setup

```
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose Network (docker0)                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │  frontend (node:20-alpine)                             ││
│  │  • npm ci && npm run dev                               ││
│  │  • Port: 5173 → 5173                                   ││
│  │  • Volume: ./frontend → /app/frontend                  ││
│  │  • Env: VITE_API_BASE_URL=http://localhost:8000       ││
│  └────────────────────────────────────────────────────────┘│
│                             │                                │
│  ┌────────────────────────────────────────────────────────┐│
│  │  app (Python 3.11)                                     ││
│  │  • uvicorn app.main:app                                ││
│  │  • Port: 8000 → 8000                                   ││
│  │  • Volume: ./ → /app                                   ││
│  │  • Depends: redis                                      ││
│  │  • Env: REDIS_URL=redis://redis:6379/0                ││
│  └────────────────────────────────────────────────────────┘│
│                             │                                │
│  ┌────────────────────────────────────────────────────────┐│
│  │  redis (redis:7-alpine)                                ││
│  │  • redis-server --save "" --appendonly no              ││
│  │  • Port: 6379 → 6379                                   ││
│  │  • No persistence (dev mode)                           ││
│  └────────────────────────────────────────────────────────┘│
│                                                              │
│  External (host):                                            │
│  • Ollama: localhost:11434 (not containerized)              │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Production Kubernetes Setup

```
┌─────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                          │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │  Ingress Controller (NGINX)                            ││
│  │  • SSL Termination (cert-manager)                      ││
│  │  • Load Balancing                                       ││
│  │  • Rate Limiting                                        ││
│  │  • WAF Rules                                            ││
│  └──────────────────────┬─────────────────────────────────┘│
│                         │                                    │
│        ┌────────────────┼────────────────┐                  │
│        │                │                │                  │
│        ▼                ▼                ▼                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│  │ Backend  │    │ Backend  │    │ Backend  │  (3 replicas)│
│  │  Pod 1   │    │  Pod 2   │    │  Pod 3   │             │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘             │
│       │               │               │                     │
│       └───────────────┼───────────────┘                     │
│                       │                                      │
│       ┌───────────────┼───────────────┐                     │
│       │               │               │                     │
│       ▼               ▼               ▼                     │
│  ┌─────────┐    ┌─────────┐    ┌─────────────┐            │
│  │  Redis  │    │  PgSQL  │    │   Ollama    │            │
│  │ Cluster │    │ Primary │    │ GPU Server  │            │
│  │(3 nodes)│    │(+replica)│   │(External)   │            │
│  └─────────┘    └─────────┘    └─────────────┘            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │  ConfigMap / Secrets                                   ││
│  │  • REDIS_URL, DATABASE_URL                             ││
│  │  • OLLAMA_BASE_URL                                     ││
│  │  • API Keys (sealed secrets)                           ││
│  └────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │  Persistent Volumes                                    ││
│  │  • Redis: RDB snapshots                                ││
│  │  • PostgreSQL: Data directory                          ││
│  └────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌────────────────────────────────────────────────────────┐│
│  │  Monitoring Stack                                      ││
│  │  • Prometheus (metrics)                                ││
│  │  • Grafana (dashboards)                                ││
│  │  • Langfuse (LLM observability)                        ││
│  │  • Jaeger (distributed tracing)                        ││
│  └────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SECURITY LAYERS                          │
└─────────────────────────────────────────────────────────────┘

Layer 1: Network Security
┌─────────────────────────────────────────────────────────────┐
│  • HTTPS Only (TLS 1.3)                                      │
│  • CORS Policy (whitelist origins)                          │
│  • Rate Limiting (per IP/user)                              │
│  • DDoS Protection (CloudFlare/AWS Shield)                  │
│  • Firewall Rules (allow specific ports only)               │
└─────────────────────────────────────────────────────────────┘

Layer 2: Authentication & Authorization (Future)
┌─────────────────────────────────────────────────────────────┐
│  • JWT-based auth (short-lived tokens)                      │
│  • OAuth2 integration (Google, GitHub)                      │
│  • API key for programmatic access                          │
│  • Role-based access control (RBAC)                         │
│  • Session management (Redis)                               │
└─────────────────────────────────────────────────────────────┘

Layer 3: Input Validation
┌─────────────────────────────────────────────────────────────┐
│  Frontend:                                                   │
│  • React XSS protection (built-in escaping)                 │
│  • Form validation (regex, length limits)                   │
│  • Sanitization (DOMPurify for user content)                │
│                                                              │
│  Backend:                                                    │
│  • Pydantic models (type checking)                          │
│  • DataValidator (custom validation)                        │
│  • SQL injection prevention (ORM only)                      │
│  • Command injection prevention (no shell calls)            │
└─────────────────────────────────────────────────────────────┘

Layer 4: Data Security
┌─────────────────────────────────────────────────────────────┐
│  • Secrets in environment variables only                    │
│  • API keys in Kubernetes Secrets (encrypted at rest)       │
│  • Database encryption (PostgreSQL encryption)              │
│  • Redis AUTH password                                      │
│  • No sensitive data in logs                                │
│  • Regular secret rotation                                  │
└─────────────────────────────────────────────────────────────┘

Layer 5: Application Security
┌─────────────────────────────────────────────────────────────┐
│  • Dependency scanning (npm audit, safety)                  │
│  • Container scanning (Trivy, Snyk)                         │
│  • SAST (static analysis - Bandit, ESLint)                  │
│  • Regular updates (automated Dependabot)                   │
│  • Minimal container images (distroless)                    │
└─────────────────────────────────────────────────────────────┘

Layer 6: Monitoring & Incident Response
┌─────────────────────────────────────────────────────────────┐
│  • Audit logging (all critical actions)                     │
│  • Anomaly detection (unusual patterns)                     │
│  • Alert system (PagerDuty, Slack)                          │
│  • Incident response plan                                   │
│  • Regular security audits                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Technology Decision Matrix

```
┌───────────────┬─────────────────┬──────────────┬──────────────┐
│ Component     │ Technology      │ Alternatives │ Why Chosen   │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Backend       │ FastAPI         │ Flask,       │ • Async-first│
│ Framework     │                 │ Django       │ • Fast       │
│               │                 │              │ • Auto docs  │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Workflow      │ LangGraph       │ Airflow,     │ • AI-native  │
│ Orchestration │                 │ Prefect      │ • State mgmt │
│               │                 │              │ • LLM integ. │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ LLM           │ Ollama          │ OpenAI,      │ • Local      │
│               │ (Gemma3)        │ Anthropic    │ • Private    │
│               │                 │              │ • No cost    │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Frontend      │ React 19        │ Vue, Svelte  │ • Ecosystem  │
│ Framework     │                 │              │ • Mature     │
│               │                 │              │ • Hiring     │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Build Tool    │ Vite 7          │ Webpack,     │ • Fast HMR   │
│               │                 │ Parcel       │ • Modern     │
│               │                 │              │ • Simple     │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Styling       │ Tailwind CSS 4  │ CSS Modules, │ • Utility-1st│
│               │                 │ styled-comp. │ • Consistent │
│               │                 │              │ • Minimal JS │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Cache         │ Redis 7         │ Memcached,   │ • Fast       │
│               │                 │ DynamoDB     │ • Versatile  │
│               │                 │              │ • Reliable   │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Database      │ SQLite →        │ MySQL,       │ • Simple dev │
│ (Future)      │ PostgreSQL      │ MongoDB      │ • Prod: PgSQL│
│               │                 │              │ • ACID       │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Financial     │ yfinance        │ Alpha Vantage│ • Free       │
│ Data          │                 │ Quandl       │ • Reliable   │
│               │                 │              │ • Simple API │
├───────────────┼─────────────────┼──────────────┼──────────────┤
│ Observability │ Langfuse        │ LangSmith,   │ • LLM-focus  │
│               │                 │ Weights&Bias │ • Open src   │
│               │                 │              │ • Self-hosted│
└───────────────┴─────────────────┴──────────────┴──────────────┘
```

---

## 9. Development Workflow & Scripts

### Development Scripts

The project includes enhanced shell scripts for streamlined development:

**scripts/start.sh - Start Services**
```bash
./scripts/start.sh

Output:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Starting EquiSense AI Stock Research Platform
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ Virtual environment activated

Starting Backend (FastAPI)...
Starting Frontend (React + Vite)...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🚀 Services Started Successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📊 Frontend UI:  http://localhost:5173
  🔌 Backend API:  http://localhost:8000
  📖 API Docs:     http://localhost:8000/docs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Press Ctrl+C to stop both services
```

**Features:**
- Auto-loads Homebrew environment (Node.js, npm)
- Activates Python virtual environment automatically
- Starts both services concurrently
- Displays clear URLs for all endpoints
- Waits 3 seconds to ensure services are ready

**scripts/stop.sh - Stop Services**
```bash
./scripts/stop.sh [backend|frontend|all]

# Stop both (default)
./scripts/stop.sh

# Stop only backend
./scripts/stop.sh backend

# Stop only frontend
./scripts/stop.sh frontend
```

**Features:**
- Graceful shutdown with SIGTERM
- Automatic SIGKILL escalation if needed
- Port-based PID detection (fallback to pattern matching)
- Compatible with both bash and zsh
- Shows process details before stopping

**scripts/pids.sh - Process Management**
```bash
./scripts/pids.sh
# Shows PIDs and details of running services
```

**scripts/dev.sh - Development Utilities**
```bash
./scripts/dev.sh
# Development helper commands
```

### Project File Organization

**Cleaned Structure:**
```
equisense-ai/
├── .venv/                          # Python virtual environment (git-ignored)
├── agentic-stock-research/         # Main application
│   ├── app/                        # Backend source
│   ├── frontend/                   # Frontend source
│   ├── tests/                      # All tests (consolidated)
│   └── docs/                       # Additional docs
├── scripts/                        # Utility scripts
├── .gitignore                      # Comprehensive ignore patterns
├── pyproject.toml                  # Python dependencies
├── docker-compose.yml              # Docker orchestration
├── README.md                       # Quick start guide
├── ARCHITECTURE.md                 # This document
├── DESIGN.md                       # Detailed design doc
└── PROJECT_STRUCTURE.md            # Structure guide
```

**Removed/Cleaned:**
- ✗ `tests/` (root) - consolidated into `agentic-stock-research/tests/`
- ✗ `app.db` - database files are now git-ignored
- ✗ `*.egg-info/` - build artifacts are git-ignored
- ✗ `Modelfile` (root) - removed outdated config
- ✗ `package-lock.json` (root) - frontend manages its own
- ✗ `response.txt` - temporary files removed

**Enhanced .gitignore:**
- Comprehensive Python patterns (__pycache__, *.pyc, etc.)
- Database files (*.db, *.sqlite)
- IDE files (.vscode/, .idea/)
- OS files (.DS_Store, Thumbs.db)
- Build artifacts (dist/, build/, *.egg-info/)
- Node modules
- Log files

### Development Dependencies

**Python Requirements (pyproject.toml):**
- Python 3.11+ required
- All dependencies managed via pip
- Editable install: `pip install -e .`

**Note on pandas-ta:**
The project does NOT require `pandas-ta` (removed from dependencies).
Technical indicators use custom implementations in `app/utils/technical_indicators.py`
with automatic fallback if pandas-ta is unavailable.

**Frontend Requirements:**
- Node.js (installed via Homebrew)
- npm packages managed via `package.json`
- Vite 7 for fast development builds

### Quick Start Commands

```bash
# First time setup
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cd agentic-stock-research/frontend && npm install && cd ../..

# Start services
./scripts/start.sh

# Stop services
./scripts/stop.sh

# Run tests
pytest agentic-stock-research/tests/

# Check running processes
./scripts/pids.sh
```

---

**Document Version:** 1.1  
**Last Updated:** October 10, 2025  
**Maintained By:** EquiSense AI Team

**Recent Updates:**
- Cleaned up project structure and removed unnecessary files
- Updated scripts with better user experience and compatibility
- Enhanced documentation with PROJECT_STRUCTURE.md
- Consolidated test structure under agentic-stock-research/tests/

