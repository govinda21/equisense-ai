# EquiSense AI - High-Level Design Document

**Version:** 1.1  
**Last Updated:** October 10, 2025  
**Document Status:** Active

**Recent Updates:**
- Cleaned up project structure and removed build artifacts
- Enhanced scripts/start.sh with better UX and auto-environment loading
- Fixed scripts/stop.sh for bash/zsh compatibility
- Removed pandas-ta dependency (using custom implementations)
- Consolidated all tests under agentic-stock-research/tests/
- Added comprehensive PROJECT_STRUCTURE.md documentation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Component Design](#3-component-design)
4. [Data Flow Architecture](#4-data-flow-architecture)
5. [LangGraph Workflow Design](#5-langgraph-workflow-design)
6. [API Design](#6-api-design)
7. [Data Architecture](#7-data-architecture)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Security Design](#9-security-design)
10. [Performance & Scalability](#10-performance--scalability)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Observability & Monitoring](#12-observability--monitoring)
13. [Future Enhancements](#13-future-enhancements)
14. [Development Environment](#14-development-environment)

---

## 1. Executive Summary

### 1.1 Purpose
EquiSense AI is a production-grade, AI-powered stock research platform that provides comprehensive equity analysis through an orchestrated multi-agent system. It combines quantitative analysis, sentiment analysis, and LLM-driven insights to generate actionable investment recommendations.

### 1.2 Key Objectives
- Provide comprehensive stock analysis across 13+ analysis dimensions
- Support international markets (US, India, UK, Canada, etc.)
- Deliver real-time AI-powered financial chat assistance
- Ensure sub-60-second analysis for single-ticker queries
- Maintain 99%+ uptime with graceful degradation

### 1.3 Technology Stack Summary

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 19, TypeScript, Vite 7, Tailwind CSS 4, React Query |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **AI/ML** | LangGraph, LangChain, Ollama (Gemma3:4b), Transformers |
| **Data Sources** | Yahoo Finance, YouTube API, Web Scraping |
| **Caching** | Redis 7 |
| **Database** | SQLite (SQLAlchemy + aiosqlite) |
| **Observability** | Langfuse, Structlog |
| **Deployment** | Docker, Docker Compose |

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  React Frontend (Port 5173)                                   │  │
│  │  - Stock Analysis UI                                          │  │
│  │  - AI Chat Interface                                          │  │
│  │  - Real-time Results Dashboard                                │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────────┼─────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Backend (Port 8000)                                  │  │
│  │  ┌────────────┬─────────────┬──────────────┬──────────────┐  │  │
│  │  │   API      │   Graph     │   Tools      │   Cache      │  │  │
│  │  │  Endpoints │  Workflow   │   Layer      │   Manager    │  │  │
│  │  └────────────┴─────────────┴──────────────┴──────────────┘  │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────────┼─────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                │             │             │
                ▼             ▼             ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│   AI/ML LAYER    │ │  DATA LAYER  │ │  CACHE LAYER     │
│                  │ │              │ │                  │
│  ┌────────────┐  │ │ ┌──────────┐ │ │  ┌───────────┐  │
│  │  Ollama    │  │ │ │  SQLite  │ │ │  │   Redis   │  │
│  │  (LLM)     │  │ │ │   DB     │ │ │  │  Cache    │  │
│  └────────────┘  │ │ └──────────┘ │ │  └───────────┘  │
│                  │ │              │ │                  │
│  ┌────────────┐  │ │ External APIs│ │  TTL: 15m-1h    │
│  │ LangGraph  │  │ │ - yfinance   │ │                  │
│  │  Workflow  │  │ │ - YouTube    │ │                  │
│  └────────────┘  │ │ - News Sites │ │                  │
└──────────────────┘ └──────────────┘ └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ OBSERVABILITY    │
                    │                  │
                    │  - Langfuse      │
                    │  - Logs          │
                    │  - Metrics       │
                    └──────────────────┘
```

### 2.2 Architecture Principles

1. **Separation of Concerns**: Clear boundaries between presentation, business logic, and data layers
2. **Async-First**: Non-blocking I/O throughout the stack
3. **Fail-Safe**: Circuit breakers, retries, and graceful degradation
4. **Stateless Services**: Horizontally scalable components
5. **Cache-First**: Minimize external API calls
6. **Observable**: Comprehensive logging and tracing

### 2.3 Communication Patterns

- **Frontend ↔ Backend**: RESTful HTTP/JSON
- **Backend ↔ Redis**: TCP (redis-py async)
- **Backend ↔ Ollama**: HTTP (streaming/non-streaming)
- **Backend ↔ External APIs**: HTTP with retries and circuit breakers

---

## 3. Component Design

### 3.1 Backend Components

#### 3.1.1 API Layer (`app/main.py`)

**Responsibilities:**
- HTTP request handling
- Request validation (Pydantic)
- Response serialization (ORJSON)
- CORS middleware
- Error handling and logging
- Performance monitoring

**Key Endpoints:**
```python
POST /analyze          # Main stock analysis
POST /api/chat         # AI chat interface
GET  /countries        # Supported countries
GET  /health           # Health check
GET  /performance      # Performance metrics
GET  /debug            # Environment debug
```

#### 3.1.2 Graph Workflow Layer (`app/graph/`)

**Responsibilities:**
- Orchestrate multi-node analysis workflow
- Manage state transitions
- Handle parallel execution
- Coordinate node dependencies

**Key Components:**
- `workflow.py`: LangGraph DAG builder
- `state.py`: ResearchState TypedDict with annotations
- `nodes/`: 14 specialized analysis nodes

**State Management:**
```python
class ResearchState(TypedDict):
    tickers: List[str]              # Accumulate with operator.add
    country: str                    # Keep last with custom reducer
    raw_data: Dict[str, Any]        # Merge with operator.or_
    analysis: Dict[str, Any]        # Merge with operator.or_
    confidences: Dict[str, float]   # Merge with operator.or_
    retries: Dict[str, int]         # Merge with operator.or_
    final_output: Dict[str, Any]    # Direct assignment
    needs_rerun: List[str]          # Accumulate with operator.add
```

#### 3.1.3 Tools Layer (`app/tools/`)

**Responsibilities:**
- Data fetching and transformation
- External API integration
- Business logic implementation
- Data validation

**Key Tools:**
- `finance.py`: Yahoo Finance integration (OHLCV, company info)
- `nlp.py`: Ollama LLM interface, sentiment analysis
- `news.py`: Web scraping for news articles
- `youtube.py`: YouTube video analysis
- `ticker_mapping.py`: International ticker resolution
- `fundamentals.py`, `valuation.py`, etc.: Specialized analysis

#### 3.1.4 Cache Layer (`app/cache/`)

**Responsibilities:**
- Reduce external API calls
- Improve response times
- Handle cache invalidation

**Cache Strategy:**
```python
Cache Type              TTL         Key Pattern
─────────────────────────────────────────────────
OHLCV Data             15 min      ohlcv:{ticker}:{period}:{interval}
Company Info           1 hour      info:{ticker}
News Sentiment         30 min      news:{ticker}:{date}
YouTube Analysis       2 hours     youtube:{ticker}:{date}
```

#### 3.1.5 Utils Layer (`app/utils/`)

**Responsibilities:**
- Async utilities and concurrency control
- Retry logic with exponential backoff
- Circuit breaker implementation
- Data validation
- Technical indicator calculations

**Key Utilities:**
- `async_utils.py`: AsyncProcessor, performance monitoring
- `retry.py`: Decorators for retry and circuit breaker
- `validation.py`: Input/output validation
- `technical_indicators.py`: TA calculations

### 3.2 Frontend Components

#### 3.2.1 Core Application (`App.tsx`)

**Responsibilities:**
- Application state management
- Form handling and validation
- API communication
- Error handling
- Layout orchestration

#### 3.2.2 UI Components (`components/`)

```
Component                Purpose
────────────────────────────────────────────────────────────
ChatInterface           AI chat with context awareness
ResultSummaryGrid       Display analysis results in grid
TabbedReportViewer      Tabbed interface for reports
TechnicalChart          Chart.js integration for technicals
LoadingStates           Spinners, progress bars, overlays
ErrorStates             Categorized error displays
Toast                   Notification system
BrandedLoader           Custom loading animation
MetricTooltip           Hover tooltips for metrics
Navbar                  Application navigation
```

#### 3.2.3 Hooks (`hooks/`)

**Custom Hooks:**
- `useCountries.ts`: Fetch and manage country list
- (Future): `useStockAnalysis`, `useChat`, `usePerformance`

---

## 4. Data Flow Architecture

### 4.1 Stock Analysis Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT                                                    │
│    Tickers: ["AAPL", "MSFT"]                                    │
│    Country: "United States"                                      │
│    Horizons: 30d, 365d                                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. FRONTEND VALIDATION                                           │
│    - Check ticker count (max 5)                                 │
│    - Validate horizon ranges                                    │
│    - Format tickers                                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼ HTTP POST /analyze
┌─────────────────────────────────────────────────────────────────┐
│ 3. API LAYER                                                     │
│    - Pydantic validation (AnalysisRequest)                      │
│    - Ticker mapping (JIOFIN → JIOFIN.NS)                       │
│    - Create Langfuse trace                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. LANGGRAPH WORKFLOW                                           │
│                                                                  │
│    START                                                         │
│      ↓                                                           │
│    DATA_COLLECTION (parallel OHLCV + info fetch)                │
│      ↓                                                           │
│    ┌─────────────┬──────────────┬───────────┬──────────┐       │
│    │ TECHNICAL   │ FUNDAMENTALS │ NEWS      │ YOUTUBE  │       │
│    │ ANALYSIS    │ ANALYSIS     │ SENTIMENT │ ANALYSIS │       │
│    └──────┬──────┴──────┬───────┴─────┬─────┴────┬─────┘       │
│           │             ↓             │          │              │
│           │      PEER_ANALYSIS        │          │              │
│           │             ↓             │          │              │
│           │  ANALYST_RECOMMENDATIONS  │          │              │
│           │             ↓             │          │              │
│           └──────→ CASHFLOW ←─────────┴──────────┘              │
│                       ↓                                          │
│                  LEADERSHIP                                      │
│                       ↓                                          │
│                 SECTOR_MACRO                                     │
│                       ↓                                          │
│              GROWTH_PROSPECTS                                    │
│                       ↓                                          │
│                  VALUATION                                       │
│                       ↓                                          │
│                  SYNTHESIS (LLM decision)                        │
│                       ↓                                          │
│                     END                                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. RESPONSE ASSEMBLY                                            │
│    - ResearchResponse model                                     │
│    - TickerReport for each ticker                              │
│    - Decision: Buy/Hold/Sell                                    │
│    - Confidence scores                                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼ JSON Response
┌─────────────────────────────────────────────────────────────────┐
│ 6. FRONTEND RENDERING                                           │
│    - Parse response                                             │
│    - Display in tabbed interface                                │
│    - Render charts                                              │
│    - Show final recommendation                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Chat Flow

```
User Query → Frontend → POST /api/chat → Stock Detection?
                                              │
                        ┌─────────────────────┴──────────────────┐
                        │                                         │
                       YES                                       NO
                        │                                         │
                        ▼                                         ▼
              Fetch Real-time Data                    Send to Ollama LLM
              from Yahoo Finance                       for General Response
                        │                                         │
                        └─────────────────────┬───────────────────┘
                                              │
                                              ▼
                                    Format & Return Response
                                              │
                                              ▼
                                    Frontend Display
```

---

## 5. LangGraph Workflow Design

### 5.1 Workflow Graph Structure

The LangGraph workflow is a **Directed Acyclic Graph (DAG)** with 14 nodes:

```python
graph = StateGraph(ResearchState)

# Entry point
graph.set_entry_point("start")

# Sequential foundation
graph.add_edge("start", "data_collection")

# Parallel fan-out from data_collection
graph.add_edge("data_collection", "technicals")
graph.add_edge("data_collection", "fundamentals")
graph.add_edge("data_collection", "news_sentiment")
graph.add_edge("data_collection", "youtube")

# Sequential dependency chain
graph.add_edge("fundamentals", "peer_analysis")
graph.add_edge("peer_analysis", "analyst_recommendations")

# Parallel fan-in to cashflow
graph.add_edge("technicals", "cashflow")
graph.add_edge("analyst_recommendations", "cashflow")
graph.add_edge("news_sentiment", "cashflow")
graph.add_edge("youtube", "cashflow")

# Final sequential chain
graph.add_edge("cashflow", "leadership")
graph.add_edge("leadership", "sector_macro")
graph.add_edge("sector_macro", "growth_prospects")
graph.add_edge("growth_prospects", "valuation")
graph.add_edge("valuation", "synthesis")
graph.add_edge("synthesis", END)
```

### 5.2 Node Execution Model

**Execution Strategy:**
- **Parallel Execution**: Nodes with no dependencies execute concurrently
- **State Accumulation**: Each node updates the shared state
- **Error Isolation**: Node failures don't cascade (graceful degradation)
- **Retry Logic**: Per-node retry tracking in state

**Example Parallel Execution:**
```
Time →
T0: [start]
T1: [data_collection]
T2: [technicals, fundamentals, news_sentiment, youtube]  ← Parallel
T3: [peer_analysis]
T4: [analyst_recommendations]
T5: [cashflow]
...
```

### 5.3 State Reducers

LangGraph uses custom reducers to merge state updates:

```python
# Accumulate tickers from multiple nodes
tickers: Annotated[List[str], operator.add]

# Keep the last country value
country: Annotated[str, _keep_last_country]

# Merge dictionaries (union)
raw_data: Annotated[Dict[str, Any], operator.or_]
analysis: Annotated[Dict[str, Any], operator.or_]
confidences: Annotated[Dict[str, float], operator.or_]
```

### 5.4 Node Design Pattern

Each node follows a consistent pattern:

```python
async def node_name(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    1. Extract required data from state
    2. Perform analysis (with error handling)
    3. Update state with results
    4. Set confidence score
    5. Return updated state
    """
    ticker = state["tickers"][0]
    
    try:
        # Fetch data from tools
        result = await analyze_something(ticker)
        
        # Update state
        state.setdefault("analysis", {})[node_name] = result
        state.setdefault("confidences", {})[node_name] = 0.9
        
    except Exception as e:
        logger.error(f"Node {node_name} failed: {e}")
        state.setdefault("confidences", {})[node_name] = 0.0
        # Graceful degradation - don't propagate exception
    
    return state
```

---

## 6. API Design

### 6.1 REST API Specification

#### 6.1.1 POST `/analyze`

**Purpose:** Perform comprehensive stock analysis

**Request:**
```json
{
  "tickers": ["AAPL", "MSFT"],
  "country": "United States",
  "horizon_short_days": 30,
  "horizon_long_days": 365
}
```

**Response:**
```json
{
  "tickers": ["AAPL", "MSFT"],
  "reports": [
    {
      "ticker": "AAPL",
      "news_sentiment": {
        "summary": "Overall positive sentiment...",
        "confidence": 0.85,
        "details": { "score": 0.72, "articles": [...] }
      },
      "technicals": { ... },
      "fundamentals": { ... },
      "peer_analysis": { ... },
      "analyst_recommendations": { ... },
      "cashflow": { ... },
      "leadership": { ... },
      "sector_macro": { ... },
      "growth_prospects": { ... },
      "valuation": { ... },
      "decision": {
        "action": "Buy",
        "rating": 4.2,
        "expected_return_pct": 15.5,
        "top_reasons_for": ["Strong fundamentals", "Positive technicals"],
        "top_reasons_against": ["High valuation", "Market volatility"]
      }
    }
  ],
  "generated_at": "2025-10-08T10:30:00Z"
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid request (validation error)
- `422`: Unprocessable entity (Pydantic validation)
- `500`: Internal server error

#### 6.1.2 POST `/api/chat`

**Purpose:** AI-powered financial chat

**Request:**
```json
{
  "message": "What is the current price of AAPL?",
  "context": ""
}
```

**Response:**
```json
{
  "response": "**Apple Inc. (AAPL)**\n\n**Current Price:** $178.50\n**Daily Change:** 📈 $+2.30 (+1.31%)\n..."
}
```

#### 6.1.3 GET `/countries`

**Response:**
```json
{
  "countries": [
    "United States",
    "India",
    "United Kingdom",
    "Canada",
    ...
  ]
}
```

### 6.2 Error Response Format

```json
{
  "detail": "Error message",
  "message": "User-friendly description",
  "error_type": "validation|network|server",
  "request_id": "uuid",
  "timestamp": "2025-10-08T10:30:00Z"
}
```

---

## 7. Data Architecture

### 7.1 Data Sources

#### 7.1.1 Yahoo Finance (yfinance)

**Data Types:**
- **OHLCV**: Historical price and volume data
- **Company Info**: Fundamentals, metrics, company details
- **Analyst Data**: Recommendations, price targets

**Access Pattern:**
```python
# OHLCV with caching
df = await fetch_ohlcv(ticker, period="1y", interval="1d")
# Returns: pandas DataFrame with [Open, High, Low, Close, Volume]

# Company info with caching
info = await fetch_info(ticker)
# Returns: Dict with 100+ fields (PE, marketCap, etc.)
```

**Rate Limits:** None enforced by yfinance, but we apply internal throttling

#### 7.1.2 News Sources (Web Scraping)

**Sources:**
- Google News
- Yahoo Finance News
- Other financial news sites

**Access Pattern:** BeautifulSoup + Playwright for dynamic content

#### 7.1.3 YouTube API (Optional)

**Data:** Video metadata, transcripts, comments

**Rate Limits:** 10,000 units/day (configurable with API key)

### 7.2 Database Schema (SQLite)

**Current Status:** Database layer is prepared but minimally used

**Planned Tables:**

```sql
-- User analysis history
CREATE TABLE analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    tickers TEXT,  -- JSON array
    country TEXT,
    request_payload TEXT,  -- JSON
    response_payload TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cached analysis results
CREATE TABLE cached_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    country TEXT,
    analysis_data TEXT,  -- JSON
    confidence_score REAL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, country)
);

-- Performance metrics
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    duration_ms REAL,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User preferences (future)
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    default_country TEXT,
    favorite_tickers TEXT,  -- JSON array
    theme TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7.3 Cache Schema (Redis)

**Key Patterns:**

```redis
# OHLCV data (TTL: 15 minutes)
ohlcv:{ticker}:{period}:{interval} → Pickled pandas DataFrame

# Company info (TTL: 1 hour)
info:{ticker} → JSON string

# News sentiment (TTL: 30 minutes)
news:{ticker}:{date} → JSON string

# YouTube analysis (TTL: 2 hours)
youtube:{ticker}:{date} → JSON string

# Performance metrics
perf:{operation}:count → Integer
perf:{operation}:total_time → Float
perf:{operation}:last_updated → Timestamp
```

---

## 8. Frontend Architecture

### 8.1 Component Hierarchy

```
App (with ErrorBoundary & ToastProvider)
├── Navbar
└── AppContent
    ├── Header
    │   └── Chat Toggle Button
    ├── Main Content Area (conditional width)
    │   ├── Analysis Form
    │   │   ├── Country Select
    │   │   ├── Ticker Input
    │   │   ├── Horizon Inputs
    │   │   └── Submit Button
    │   ├── Progress Bar (when loading)
    │   ├── Error State (when error)
    │   ├── Empty State (when no data)
    │   └── Results (with LoadingOverlay)
    │       └── ResultSummaryGrid (per ticker)
    │           ├── Decision Card
    │           ├── TabbedReportViewer
    │           │   ├── Technical Tab → TechnicalChart
    │           │   ├── Fundamentals Tab
    │           │   ├── Sentiment Tab
    │           │   ├── Peer Analysis Tab
    │           │   ├── Analyst Recommendations Tab
    │           │   ├── Cashflow Tab
    │           │   ├── Growth Tab
    │           │   ├── Valuation Tab
    │           │   └── More...
    │           └── Metric Cards with Tooltips
    └── Chat Panel (conditional render)
        └── ChatInterface
            ├── Message List
            ├── Input Field
            └── Send Button
```

### 8.2 State Management Strategy

**Local State (useState):**
- Form inputs (tickers, country, horizons)
- UI state (loading, error, chatOpen)
- Analysis results (data)
- Performance metrics (latency)

**Server State (React Query - future enhancement):**
- Countries list
- Analysis results with caching
- Chat history

**Context (Future):**
- Theme preferences
- User settings
- Global notifications

### 8.3 Data Fetching Strategy

**Current Approach:** Native `fetch` API with manual error handling

**Fetch Pattern:**
```typescript
const controller = new AbortController()
const timeoutId = setTimeout(() => controller.abort(), 120000)

const res = await fetch(baseURL + '/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
  signal: controller.signal
})

clearTimeout(timeoutId)
```

**Future Enhancement:** React Query for:
- Automatic retries
- Request deduplication
- Background refetching
- Optimistic updates

### 8.4 Error Handling Strategy

**Error Categorization:**
```typescript
type ErrorType = 'network' | 'server' | 'validation' | 'generic'

// Network errors: Connection refused, DNS issues, timeout
// Server errors: 500, 502, 503, 504
// Validation errors: 400, 422
// Generic errors: Unexpected issues
```

**Error Display:**
- Visual error states with icons
- Actionable retry buttons
- Detailed error messages
- Toast notifications

---

## 9. Security Design

### 9.1 Input Validation

**Frontend Validation:**
- Ticker format validation (alphanumeric + dots)
- Ticker count limits (max 5)
- Horizon range validation (1-1825 days)
- XSS prevention (React's built-in escaping)

**Backend Validation:**
- Pydantic models for request validation
- Ticker sanitization in `DataValidator`
- SQL injection prevention (SQLAlchemy ORM)
- Rate limiting (configurable)

### 9.2 API Security

**Current Measures:**
- CORS configuration (allow all origins - should be restricted in production)
- Request timeout enforcement
- Input sanitization
- Error message sanitization (no stack traces to client)

**Production Requirements:**
- API key authentication
- JWT-based user sessions
- Rate limiting per user/IP
- HTTPS enforcement
- CORS restricted to frontend domain

### 9.3 Data Privacy

**Sensitive Data:**
- API keys stored in environment variables
- No user data stored (currently stateless)
- Cache data expires automatically

**Future Considerations:**
- User authentication system
- GDPR compliance for EU users
- Data encryption at rest
- Audit logging

### 9.4 Dependency Security

**Practices:**
- Regular dependency updates
- Vulnerability scanning (npm audit, safety)
- Minimal dependency footprint
- Pinned versions in production

---

## 10. Performance & Scalability

### 10.1 Performance Optimizations

#### Backend Optimizations

1. **Async I/O:**
   - All network calls use `asyncio`
   - Concurrent execution with `asyncio.gather`
   - Non-blocking database operations

2. **Caching Strategy:**
   ```
   Cache Hit Rate Target: >80%
   Average Response Time: <2s (with cache)
   Average Response Time: <60s (without cache)
   ```

3. **Connection Pooling:**
   - Redis connection pool
   - HTTP connection reuse
   - Database connection pool (future)

4. **Parallel Execution:**
   - LangGraph parallel nodes (4 concurrent in data collection phase)
   - AsyncProcessor with configurable workers (default: 5)
   - Concurrency limits to prevent resource exhaustion

5. **Data Serialization:**
   - ORJSON for fast JSON encoding
   - Pickle for Redis DataFrame storage
   - Minimal data transformation

#### Frontend Optimizations

1. **Code Splitting:**
   - Vite's automatic code splitting
   - Lazy loading for heavy components
   - Tree shaking for unused code

2. **Asset Optimization:**
   - SVG icons (minimal size)
   - No external fonts (system fonts)
   - Minimal CSS bundle with Tailwind

3. **Rendering Optimization:**
   - React memoization (future)
   - Virtual scrolling for large datasets (future)
   - Debounced input handlers

### 10.2 Scalability Considerations

#### Horizontal Scalability

**Stateless Design:**
- Backend instances are stateless
- Session state in Redis (future)
- Shared nothing architecture

**Load Balancing Ready:**
```
                    ┌──→ Backend Instance 1
Internet → LB/Nginx ┼──→ Backend Instance 2
                    └──→ Backend Instance N
                            ↓
                       Shared Redis
```

#### Vertical Scalability

**Resource Limits:**
- Each analysis: ~200MB RAM
- Ollama model: ~4GB RAM
- Redis: ~512MB for cache

**Bottlenecks:**
1. LLM inference (Ollama) - single-threaded
2. External API rate limits (Yahoo Finance)
3. Network I/O to data sources

#### Database Scalability

**Current:** SQLite (single file, low concurrency)

**Future Migration Path:**
```
SQLite → PostgreSQL (with connection pooling)
       → Read replicas for analytics
       → Partitioning by date/ticker
```

### 10.3 Performance Monitoring

**Metrics Tracked:**
- Per-operation latency (data_collection, analysis nodes)
- Cache hit/miss rates
- Error rates by operation
- External API response times

**Performance Endpoint:**
```bash
GET /performance
```

**Response:**
```json
{
  "operations": {
    "data_collection": {
      "count": 150,
      "total": 450.5,
      "average": 3.0,
      "min": 1.2,
      "max": 8.5
    },
    "stock_analysis": {
      "count": 50,
      "total": 2500,
      "average": 50.0,
      ...
    }
  }
}
```

---

## 11. Deployment Architecture

### 11.1 Local Development

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8000:8000"]
    depends_on: [redis]
    
  frontend:
    image: node:20-alpine
    ports: ["5173:5173"]
    
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

**Startup:**
```bash
# Option 1: Script
./scripts/dev.sh

# Option 2: Docker
docker compose up --build

# Option 3: Manual
# Terminal 1: Backend
uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Ollama
ollama serve
```

### 11.2 Production Deployment

#### Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Kubernetes Cluster / Docker Swarm                       │
│                                                          │
│  ┌────────────────┐  ┌────────────────┐                │
│  │  Backend Pod   │  │  Backend Pod   │  (Replicas: 3) │
│  │  - FastAPI     │  │  - FastAPI     │                │
│  │  - Python 3.11 │  │  - Python 3.11 │                │
│  └────────┬───────┘  └────────┬───────┘                │
│           │                   │                         │
│           └─────────┬─────────┘                         │
│                     ▼                                   │
│            ┌─────────────────┐                          │
│            │   Redis Cluster │                          │
│            │   (Persistent)  │                          │
│            └─────────────────┘                          │
│                                                          │
│  ┌────────────────────────────────┐                    │
│  │  Nginx Ingress Controller      │                    │
│  │  - SSL Termination             │                    │
│  │  - Load Balancing              │                    │
│  │  - Static File Serving         │                    │
│  └────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────┘

External Services:
- Ollama: Separate GPU server (HTTP API)
- Langfuse: Separate observability stack
- PostgreSQL: Managed database service (future)
```

#### Environment Configuration

**Production `.env`:**
```bash
ENV=production
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/equisense

# Redis
REDIS_URL=redis://redis-cluster:6379/0

# LLM
OLLAMA_BASE_URL=http://ollama-server:11434
OLLAMA_MODEL=gemma3:4b

# Observability
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://langfuse.company.com

# Performance
HTTP_TIMEOUT_SECONDS=30
REQUESTS_PER_MINUTE=60

# Security
ALLOWED_ORIGINS=https://equisense.company.com
API_KEY_REQUIRED=true
```

#### Docker Production Image

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .

# Copy application
COPY agentic-stock-research/app ./app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run with production settings
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 11.3 Deployment Checklist

**Pre-Deployment:**
- [ ] Run all tests (`pytest tests/`)
- [ ] Frontend build (`npm run build`)
- [ ] Security audit (`npm audit`, `safety check`)
- [ ] Load testing
- [ ] Backup database
- [ ] Review environment variables
- [ ] Check resource limits

**Deployment:**
- [ ] Blue-green deployment or rolling update
- [ ] Health check verification
- [ ] Smoke tests
- [ ] Monitor error rates
- [ ] Rollback plan ready

**Post-Deployment:**
- [ ] Monitor logs for errors
- [ ] Check performance metrics
- [ ] Verify cache warming
- [ ] Test critical user flows
- [ ] Update documentation

---

## 12. Observability & Monitoring

### 12.1 Logging Strategy

#### Backend Logging (structlog)

**Log Levels:**
```python
DEBUG:   Detailed diagnostic info (cache hits, data fetching)
INFO:    General informational messages (request start/end)
WARNING: Recoverable errors (failed cache, fallback logic)
ERROR:   Serious errors (node failures, API errors)
CRITICAL: System failures
```

**Log Format:**
```json
{
  "timestamp": "2025-10-08T10:30:00.123Z",
  "level": "info",
  "event": "analysis_completed",
  "ticker": "AAPL",
  "duration_ms": 1250,
  "component": "graph.synthesis",
  "trace_id": "abc123"
}
```

#### Frontend Logging

**Browser Console:**
- Error boundary catches
- API failures
- Performance warnings

**Future:** Send to backend logging service

### 12.2 Tracing (Langfuse)

**LLM Observability:**
- Trace each analysis request
- Track LLM generation (prompts, responses, latency)
- Monitor token usage
- Debug prompt engineering

**Langfuse Trace Hierarchy:**
```
Trace: stock-analysis (AAPL)
├── Span: data_collection (3.2s)
├── Span: technicals (1.5s)
├── Span: fundamentals (2.1s)
├── Span: synthesis (8.5s)
│   └── Generation: ollama-decision (8.3s)
│       ├── Input: [prompt with all analysis]
│       ├── Output: SCORE: 0.75, ACTION: Buy...
│       ├── Tokens: 1500 in, 200 out
│       └── Cost: $0.02
└── Final: Buy recommendation (rating: 4.2)
```

### 12.3 Metrics & Alerting

**Key Metrics:**
```
Business Metrics:
- Analyses per hour
- Average analysis duration
- Error rate by ticker
- Cache hit rate
- User retention (future)

Technical Metrics:
- API response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- External API latency
- LLM inference time
- Memory usage
- CPU usage
- Redis connection pool

Infrastructure Metrics:
- Container health
- Disk usage
- Network throughput
```

**Alerting Rules:**
```yaml
alerts:
  - name: high_error_rate
    condition: error_rate > 5%
    duration: 5m
    severity: critical
    
  - name: slow_api_response
    condition: p95_latency > 120s
    duration: 10m
    severity: warning
    
  - name: cache_failure
    condition: redis_unavailable
    duration: 1m
    severity: critical
    
  - name: ollama_down
    condition: ollama_health_check_failed
    duration: 2m
    severity: critical
```

### 12.4 Dashboards

**Grafana Dashboard Panels:**
1. Request Rate & Error Rate (time series)
2. Latency Distribution (histogram)
3. Cache Hit Rate (gauge)
4. Analysis Breakdown (pie chart: Buy/Hold/Sell)
5. External API Status (status grid)
6. Resource Usage (CPU, Memory)
7. LLM Performance (tokens/sec, cost)

---

## 13. Future Enhancements

### 13.1 Short-Term (Q1 2026)

1. **Multi-Ticker Concurrency**
   - Parallel analysis of multiple tickers
   - Batch processing optimization

2. **Enhanced Caching**
   - Redis Cluster for HA
   - Cache warming strategies
   - Intelligent TTL adjustment

3. **User Authentication**
   - OAuth2 integration
   - User accounts and profiles
   - Saved analysis history

4. **Advanced Charts**
   - Interactive candlestick charts
   - Technical indicator overlays
   - Zoom and pan capabilities

5. **PDF Export**
   - Generate comprehensive PDF reports
   - Email delivery option

### 13.2 Mid-Term (Q2-Q3 2026)

1. **Portfolio Management**
   - Track multiple stocks in portfolio
   - Portfolio-level metrics
   - Rebalancing recommendations

2. **Backtesting Framework**
   - Test strategies on historical data
   - Performance attribution
   - Risk analysis

3. **Alert System**
   - Price alerts
   - News alerts
   - Technical signal alerts
   - Email/SMS notifications

4. **More Markets**
   - European exchanges (LSE, Euronext, DAX)
   - Asian exchanges (TSE, HKEX)
   - Cryptocurrency integration

5. **Advanced Valuation Models**
   - Monte Carlo simulation
   - Real options valuation
   - Scenario analysis

### 13.3 Long-Term (2027+)

1. **Mobile Apps**
   - iOS and Android native apps
   - Push notifications
   - Mobile-optimized UI

2. **Social Features**
   - Share analyses
   - Follow other users
   - Collaborative research

3. **AI Improvements**
   - Fine-tuned models on financial data
   - Multi-model ensemble
   - Explainable AI (XAI)

4. **Institutional Features**
   - Team collaboration
   - Custom workflows
   - White-label solutions
   - API for third-party integration

5. **Real-Time Streaming**
   - WebSocket-based live updates
   - Real-time price feeds
   - Live news integration

---

## Appendix A: Technology Rationale

### Why LangGraph?
- **State Management**: Built-in state accumulation and merging
- **Parallel Execution**: Native support for concurrent nodes
- **Observability**: Integrates with LangSmith/Langfuse
- **Flexibility**: Easy to add/remove/modify nodes
- **Production-Ready**: Battle-tested in enterprise

### Why FastAPI?
- **Performance**: Async-native, fastest Python framework
- **Developer Experience**: Auto-generated docs, type hints
- **Validation**: Built-in Pydantic integration
- **Modern**: OpenAPI 3.1, JSON Schema

### Why React + Vite?
- **Performance**: Fast HMR, optimized builds
- **Ecosystem**: Largest component library
- **Type Safety**: First-class TypeScript support
- **Developer Experience**: Excellent tooling

### Why Redis?
- **Speed**: In-memory, sub-millisecond latency
- **Simplicity**: Simple key-value model
- **Persistence**: RDB/AOF options
- **Scalability**: Cluster mode for HA

### Why Ollama?
- **Privacy**: Local LLM, no data leaves premises
- **Cost**: No per-token charges
- **Control**: Full model customization
- **Speed**: GPU-accelerated inference

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **LangGraph** | Framework for building stateful, multi-actor applications with LLMs |
| **DAG** | Directed Acyclic Graph - workflow execution order |
| **OHLCV** | Open, High, Low, Close, Volume - candlestick data |
| **TTL** | Time To Live - cache expiration time |
| **P/E Ratio** | Price-to-Earnings ratio - valuation metric |
| **ROE** | Return on Equity - profitability metric |
| **DCF** | Discounted Cash Flow - valuation method |
| **DDM** | Dividend Discount Model - valuation method |
| **FCF** | Free Cash Flow - cash after capex |
| **OCF** | Operating Cash Flow - cash from operations |
| **NSE/BSE** | Indian stock exchanges (National/Bombay) |
| **Circuit Breaker** | Fault tolerance pattern to prevent cascading failures |

---

## Appendix C: References

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Yahoo Finance API**: https://pypi.org/project/yfinance/
- **Ollama Documentation**: https://ollama.com/
- **React Documentation**: https://react.dev/
- **Tailwind CSS**: https://tailwindcss.com/

---

## 14. Development Environment

### 14.1 Project Structure

The project follows a clean, organized structure:

```
equisense-ai/
├── agentic-stock-research/         # Main application
│   ├── app/                        # Backend (Python/FastAPI)
│   │   ├── cache/                  # Redis caching
│   │   ├── graph/                  # LangGraph workflow
│   │   │   └── nodes/              # Analysis nodes (13+ modules)
│   │   ├── schemas/                # Pydantic models
│   │   ├── tools/                  # Analysis tools
│   │   └── utils/                  # Helper functions
│   ├── frontend/                   # React/TypeScript UI
│   │   ├── src/                    # Source code
│   │   │   ├── components/         # React components
│   │   │   └── hooks/              # Custom hooks
│   │   └── package.json            # Frontend dependencies
│   ├── tests/                      # All tests (consolidated)
│   └── docs/                       # Additional documentation
│
├── scripts/                        # Utility scripts
│   ├── start.sh                    # Start backend + frontend
│   ├── stop.sh                     # Stop services gracefully
│   ├── dev.sh                      # Development utilities
│   └── pids.sh                     # Process management
│
├── pyproject.toml                  # Python dependencies
├── docker-compose.yml              # Docker orchestration
├── .gitignore                      # Git ignore (comprehensive)
├── README.md                       # Project overview
├── ARCHITECTURE.md                 # System architecture
├── DESIGN.md                       # This document
└── PROJECT_STRUCTURE.md            # Detailed structure guide
```

### 14.2 Development Scripts

**Starting Services:**
```bash
./scripts/start.sh
```
- Auto-loads Homebrew environment
- Activates Python virtual environment
- Starts backend (FastAPI) on port 8000
- Starts frontend (Vite) on port 5173
- Displays startup summary with URLs

**Stopping Services:**
```bash
./scripts/stop.sh [backend|frontend|all]
```
- Gracefully terminates processes (SIGTERM)
- Falls back to SIGKILL if needed
- Compatible with both bash and zsh
- Supports selective shutdown

### 14.3 Dependencies Management

**Python Dependencies (pyproject.toml):**
- Core: FastAPI, Uvicorn, LangGraph, LangChain
- Data: Pandas, NumPy, yfinance
- AI/ML: Transformers, Sentence-Transformers
- Database: SQLAlchemy, aiosqlite
- Caching: Redis
- Observability: Langfuse, Structlog

**Note:** pandas-ta is NOT required - the project uses custom technical indicator implementations as fallback.

**Frontend Dependencies (package.json):**
- React 19, TypeScript
- Vite 7 (build tool)
- Tailwind CSS 4
- Chart.js, React Query
- Axios for API calls

### 14.4 Environment Setup

**First-Time Setup:**
```bash
# 1. Install Python 3.11+
brew install python@3.11

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -e .

# 4. Install Node.js and frontend dependencies
brew install node
cd agentic-stock-research/frontend
npm install
cd ../..

# 5. Configure environment
cp .env.example .env  # Edit with your API keys
```

**Environment Variables (.env):**
```bash
# Required
OPENAI_API_KEY=your_key_here
LANGFUSE_SECRET_KEY=your_key_here
LANGFUSE_PUBLIC_KEY=your_key_here
LANGFUSE_HOST=https://cloud.langfuse.com

# Optional
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
```

### 14.5 Testing

**Run Tests:**
```bash
# All tests
pytest agentic-stock-research/tests/

# With coverage
pytest --cov=app agentic-stock-research/tests/

# Specific test file
pytest agentic-stock-research/tests/test_api.py
```

### 14.6 Code Quality

**Linting & Formatting:**
```bash
# Format code
black agentic-stock-research/app/

# Sort imports
isort agentic-stock-research/app/

# Check code quality
flake8 agentic-stock-research/app/
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-08 | EquiSense Team | Initial high-level design document |
| 1.1 | 2025-10-10 | EquiSense Team | Added development environment section, updated structure |

---

**End of Document**

