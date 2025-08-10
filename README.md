# EquiSense AI - Agentic Stock Research Platform

**Production-grade AI-powered stock research platform using LangGraph + FastAPI backend with React + Vite frontend. Features enhanced workflow with peer analysis, analyst consensus, growth prospects, and multi-model valuation.**

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ 
- Node.js 18+
- [Ollama](https://ollama.com/) installed and running
- Docker (optional, for Langfuse observability)

---

## 📦 One-Time Setup

### 1. Backend Setup
```bash
# Navigate to project root
cd /Users/govindak/workspace/EquiSense_AI

# Create and activate virtual environment (use the existing one)
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install -U pip setuptools wheel
pip install -e '.[dev]'

# Install browser dependencies for potential web scraping
python -m playwright install --with-deps chromium
```

### 2. Frontend Setup
```bash
# Navigate to frontend directory
cd agentic-stock-research/frontend

# Install dependencies
npm ci

# Create environment file (if it doesn't exist)
cp .env.example .env 2>/dev/null || echo "VITE_API_BASE_URL=http://localhost:8000" > .env
```

### 3. AI Model Setup
```bash
# Install Ollama model (if not already installed)
ollama pull gemma3:4b

# Verify model is available
ollama list | grep gemma3
```

### 4. Optional: Langfuse Observability Setup
```bash
# Start Langfuse (Docker required)
docker compose -f docker-compose.langfuse.yml up -d

# Create .env file in backend directory
echo "LANGFUSE_PUBLIC_KEY=your_public_key" >> agentic-stock-research/.env
echo "LANGFUSE_SECRET_KEY=your_secret_key" >> agentic-stock-research/.env
echo "LANGFUSE_HOST=http://localhost:3100" >> agentic-stock-research/.env
```

---

## 🏃‍♂️ Running the Services

### Method 1: Quick Start Script
```bash
# Run everything with one command
./scripts/dev.sh
```

### Method 2: Manual Service Startup

#### Start Backend
```bash
cd /Users/govindak/workspace/EquiSense_AI
source .venv/bin/activate

# Set environment and start backend
OLLAMA_MODEL="gemma3:4b" PYTHONPATH=/Users/govindak/workspace/EquiSense_AI/agentic-stock-research python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Or run in background
OLLAMA_MODEL="gemma3:4b" PYTHONPATH=/Users/govindak/workspace/EquiSense_AI/agentic-stock-research python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

#### Start Frontend
```bash
cd /Users/govindak/workspace/EquiSense_AI/agentic-stock-research/frontend
npm run dev

# Or run in background
npm run dev &
```

#### Start Ollama (if not running)
```bash
# Start Ollama service
ollama serve &

# Load the model
ollama run gemma3:4b
```

### Method 3: Docker (Everything)
```bash
# Build and run all services
docker compose up --build

# Or run in background
docker compose up --build -d
```

---

## 🌐 Access Points

Once all services are running:

- **🎯 Main Application**: http://localhost:5173 (Frontend)
- **🔧 Backend API**: http://localhost:8000 (FastAPI + Auto Docs)
- **📊 API Documentation**: http://localhost:8000/docs
- **🔍 Health Check**: http://localhost:8000/health
- **📈 Langfuse Dashboard**: http://localhost:3100 (if enabled)

---

## 🔧 Service Management

### Check Running Services
```bash
# Check all related processes
ps aux | grep -E "(uvicorn|npm|ollama)" | grep -v grep

# Check specific ports
lsof -i :8000  # Backend
lsof -i :5173  # Frontend
lsof -i :11434 # Ollama
```

### Stop Services
```bash
# Stop background processes
pkill -f "uvicorn"
pkill -f "npm run dev"

# Or use job control if running in foreground
# Ctrl+C in each terminal
```

### Restart Services
```bash
# Quick restart backend
cd /Users/govindak/workspace/EquiSense_AI
source .venv/bin/activate
OLLAMA_MODEL="gemma3:4b" PYTHONPATH=/Users/govindak/workspace/EquiSense_AI/agentic-stock-research python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Quick restart frontend
cd agentic-stock-research/frontend
npm run dev
```

---

## 📋 API Usage

### Stock Analysis
```bash
# Analyze US stocks
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL"], "country": "United States"}'

# Analyze Indian stocks  
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["JIOFIN"], "country": "India"}'
```

### AI Chat
```bash
# Chat with AI about stocks
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current price of AAPL?"}'
```

### Supported Countries
```bash
# Get list of supported countries
curl http://localhost:8000/countries
```

---

## 🆕 Enhanced Features

### New Analysis Modules
- **🏢 Peer Analysis**: Competitor benchmarking and relative positioning
- **📊 Analyst Recommendations**: Consensus price targets and sentiment
- **📈 Growth Prospects**: Multi-timeline growth projections (1Y/3Y/5Y+)
- **💰 Enhanced Valuation**: DCF, DDM, Comparables, Sum-of-Parts models
- **🧠 AI-Powered Synthesis**: LLM-driven investment recommendations

### International Support
- **🇺🇸 US Markets**: NYSE, NASDAQ
- **🇮🇳 Indian Markets**: NSE (.NS), BSE (.BO)
- **💱 Multi-Currency**: Automatic currency detection and formatting

---

## 🐛 Troubleshooting

### Backend Issues
```bash
# Check Python environment
which python3  # Should point to .venv/bin/python3

# Test imports
cd /Users/govindak/workspace/EquiSense_AI
source .venv/bin/activate
python3 -c "from app.main import app; print('✅ Backend imports OK')"

# Check Ollama connection
curl http://localhost:11434/api/tags

# Manual backend start with verbose logging
OLLAMA_MODEL="gemma3:4b" PYTHONPATH=/Users/govindak/workspace/EquiSense_AI/agentic-stock-research python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

### Frontend Issues
```bash
# Clear npm cache and reinstall
cd agentic-stock-research/frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

# Check environment variables
cat .env

# Build and preview production version
npm run build
npm run preview
```

### Ollama Issues
```bash
# Restart Ollama service
ollama serve

# Pull model again if corrupted
ollama pull gemma3:4b

# List available models
ollama list

# Check Ollama logs
tail -f ~/.ollama/logs/server.log
```

### Common Port Conflicts
```bash
# Find process using port 8000
lsof -ti :8000 | xargs kill -9

# Use alternative ports
# Backend: uvicorn ... --port 8001
# Frontend: npm run dev -- --port 5174
# Update VITE_API_BASE_URL accordingly
```

---

## 🧪 Testing

### Backend Tests
```bash
cd /Users/govindak/workspace/EquiSense_AI
source .venv/bin/activate
pytest tests/ -v
```

### Frontend Tests
```bash
cd agentic-stock-research/frontend
npm run test
```

### Integration Tests
```bash
# Test complete workflow
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL"], "country": "United States"}' | jq '.reports[0].decision'
```

---

## 📊 Production Deployment

### Build Production Image
```bash
# Build optimized Docker image
docker build -t equisense-ai:latest .

# Run production container
docker run -p 8000:8000 \
  -e OLLAMA_MODEL=gemma3:4b \
  -e LANGFUSE_PUBLIC_KEY=your_key \
  equisense-ai:latest
```

### Environment Variables
Create `.env` files for configuration:

**Backend** (`agentic-stock-research/.env`):
```env
OLLAMA_MODEL=gemma3:4b
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=http://localhost:3100
YOUTUBE_API_KEY=your_youtube_key  # Optional
```

**Frontend** (`agentic-stock-research/frontend/.env`):
```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 📈 Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   React Frontend│    │  FastAPI Backend │    │   Ollama LLM    │
│   (Port 5173)   │◄──►│   (Port 8000)    │◄──►│  (Port 11434)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌──────────────────┐             │
         └──────────────►│   LangGraph      │◄────────────┘
                        │   Workflow       │
                        └──────────────────┘
                                 │
                        ┌──────────────────┐
                        │  Financial APIs  │
                        │ (Yahoo Finance)  │
                        └──────────────────┘
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-analysis-node`
3. Make changes and test thoroughly
4. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

---

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Search existing GitHub issues
3. Create a new issue with detailed error logs and system info

**System Requirements:**
- macOS/Linux (Windows with WSL2)
- Python 3.11+, Node.js 18+
- 8GB+ RAM (for Ollama models)
- 10GB+ free disk space