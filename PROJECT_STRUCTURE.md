# Project Structure

EquiSense AI - Agentic Stock Research Platform

## Directory Layout

```
equisense-ai/
├── .venv/                          # Python virtual environment (local)
├── agentic-stock-research/         # Main application directory
│   ├── app/                        # Backend application code
│   │   ├── cache/                  # Caching implementations (Redis)
│   │   ├── clients/                # External API clients
│   │   ├── db/                     # Database models and utilities
│   │   ├── graph/                  # LangGraph workflow
│   │   │   ├── nodes/              # Graph nodes (analysis modules)
│   │   │   ├── state.py            # Workflow state definition
│   │   │   └── workflow.py         # Graph construction
│   │   ├── schemas/                # Pydantic models for I/O
│   │   ├── tools/                  # Analysis tools and utilities
│   │   ├── utils/                  # Helper functions
│   │   ├── config.py               # Application configuration
│   │   ├── logging.py              # Logging setup
│   │   └── main.py                 # FastAPI application entry point
│   │
│   ├── frontend/                   # React + TypeScript frontend
│   │   ├── public/                 # Static assets
│   │   ├── src/                    # Source code
│   │   │   ├── components/         # React components
│   │   │   ├── hooks/              # Custom React hooks
│   │   │   ├── App.tsx             # Main app component
│   │   │   └── main.tsx            # Entry point
│   │   ├── package.json            # Frontend dependencies
│   │   └── vite.config.ts          # Vite configuration
│   │
│   ├── docs/                       # Documentation
│   │   └── request_flow.md         # Request flow documentation
│   │
│   └── tests/                      # Test suite
│       ├── test_api.py             # API endpoint tests
│       ├── test_workflow.py        # Workflow tests
│       └── test_enhancements.py    # Feature enhancement tests
│
├── scripts/                        # Utility scripts
│   ├── start.sh                    # Start backend + frontend
│   ├── stop.sh                     # Stop services
│   ├── dev.sh                      # Development tools
│   ├── pids.sh                     # Process management
│   ├── cli.py                      # CLI utilities
│   └── gen_graph_diagram.py        # Generate workflow diagrams
│
├── .gitignore                      # Git ignore rules
├── pyproject.toml                  # Python project config & dependencies
├── docker-compose.yml              # Docker Compose configuration
├── docker-compose.langfuse.yml     # Langfuse observability setup
├── Dockerfile                      # Docker image definition
├── README.md                       # Project overview & setup
├── ARCHITECTURE.md                 # System architecture documentation
├── DESIGN.md                       # Design decisions
└── PROJECT_STRUCTURE.md            # This file

```

## Key Components

### Backend (`agentic-stock-research/app/`)

**Entry Point:** `main.py` - FastAPI application

**Graph Nodes** (`graph/nodes/`):
- `start.py` - Workflow initialization
- `data_collection.py` - Fetch stock data
- `fundamentals.py` - Fundamental analysis
- `technicals.py` - Technical analysis
- `news_sentiment.py` - News & sentiment analysis
- `analyst_recommendations.py` - Analyst ratings
- `peer_analysis.py` - Peer comparison
- `valuation.py` - Valuation metrics
- `cashflow.py` - Cash flow analysis
- `leadership.py` - Management analysis
- `sector_macro.py` - Sector & macro trends
- `growth_prospects.py` - Growth potential
- `youtube_analysis.py` - Video content analysis
- `synthesis.py` - Final report generation
- `synthesis_multi.py` - Multi-stock comparison
- `comprehensive_fundamentals.py` - Enhanced fundamentals

**Tools** (`tools/`):
- Financial data fetching (yfinance, APIs)
- NLP and sentiment analysis
- Technical indicator calculations
- Scoring and valuation models
- Data federation and integration

### Frontend (`agentic-stock-research/frontend/`)

**Technology Stack:**
- React 19
- TypeScript
- Vite (build tool)
- Tailwind CSS
- Chart.js (visualizations)
- React Query (data fetching)

**Key Components:**
- `ChatInterface.tsx` - Main interaction UI
- `TabbedReportViewer.tsx` - Report display
- `TechnicalChart.tsx` - Stock charts
- `ResultSummaryGrid.tsx` - Summary cards
- `Navbar.tsx` - Navigation

### Scripts

- **`start.sh`** - Start both backend and frontend
- **`stop.sh`** - Gracefully stop services
- **`dev.sh`** - Development utilities
- **`pids.sh`** - Process ID management

## Development Workflow

### 1. First Time Setup

```bash
# Install Python dependencies
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Install frontend dependencies
cd agentic-stock-research/frontend
npm install
```

### 2. Running the Application

```bash
# From project root
./scripts/start.sh

# Services will be available at:
# - Frontend: http://localhost:5173
# - Backend:  http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### 3. Stopping Services

```bash
./scripts/stop.sh
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

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

### Python Dependencies

Managed in `pyproject.toml`:
- FastAPI, Uvicorn (web framework)
- LangChain, LangGraph (AI orchestration)
- Pandas, NumPy (data processing)
- yfinance (financial data)
- Transformers, Sentence-Transformers (NLP)

### Frontend Dependencies

Managed in `agentic-stock-research/frontend/package.json`:
- React ecosystem
- TypeScript
- Tailwind CSS
- Chart.js for visualizations

## Testing

```bash
# Run tests
pytest agentic-stock-research/tests/

# With coverage
pytest --cov=app agentic-stock-research/tests/
```

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# With Langfuse observability
docker-compose -f docker-compose.yml -f docker-compose.langfuse.yml up
```

## Generated/Ignored Files

The following are generated locally and not tracked in git:
- `.venv/` - Python virtual environment
- `__pycache__/`, `*.pyc` - Python bytecode
- `node_modules/` - Node.js dependencies
- `*.db` - Local databases
- `*.log` - Log files
- `.egg-info/` - Build artifacts

See `.gitignore` for complete list.

## Architecture

For detailed system architecture, see [ARCHITECTURE.md](ARCHITECTURE.md)

For design decisions and patterns, see [DESIGN.md](DESIGN.md)


