# Quick Setup Guide for EquiSense AI

## 🚀 **Getting Started on New Machine**

### **1. Clone Repository**
```bash
git clone <your-repo-url>
cd equisense-ai
```

### **2. Backend Setup**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
cd agentic-stock-research
pip install -r requirements.txt

# Start backend server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### **3. Frontend Setup**
```bash
# In new terminal
cd agentic-stock-research/frontend
npm install
npm run dev
```

### **4. Optional Services**
```bash
# Redis (for caching)
brew install redis  # macOS
redis-server

# Ollama (for local LLM)
brew install ollama  # macOS
ollama serve
```

## 🔧 **Environment Configuration**

Create `.env` file in `agentic-stock-research/`:
```env
# Optional API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
OLLAMA_BASE_URL=http://localhost:11434

# Optional Redis
REDIS_URL=redis://localhost:6379

# Optional BSE API
BSE_API_KEY=your_bse_api_key
```

## 📊 **Quick Test**

1. **Backend Health**: `curl http://localhost:8000/health`
2. **Frontend**: Open `http://localhost:5173`
3. **Analysis**: Try analyzing RELIANCE (default Indian stock)

## 🎯 **Key Features Ready**

- ✅ **12 Complete Initiatives**: All competitive enhancements implemented
- ✅ **Indian Market Focus**: Default to India with RELIANCE ticker
- ✅ **Multi-Source Data**: BSE, Screener.in, MoneyControl integration
- ✅ **Advanced Analysis**: DCF, technical analysis, sentiment analysis
- ✅ **Real-time Monitoring**: Performance metrics and health scoring
- ✅ **Security**: JWT authentication and role-based access
- ✅ **API-First**: Complete REST API for all features

## 📝 **Development Notes**

- **Graceful Degradation**: System works even without optional dependencies
- **Error Handling**: Comprehensive error handling with fallbacks
- **Logging**: Structured logging in `logs/backend.log`
- **Caching**: Redis with in-memory fallback
- **Async Processing**: Non-blocking I/O throughout

## 🚀 **Next Steps**

1. **Configure API Keys**: Add your API keys for enhanced functionality
2. **Set up Redis**: For production-level caching
3. **Test Analysis**: Run analysis on various Indian stocks
4. **Customize UI**: Modify frontend components as needed
5. **Deploy**: Consider cloud deployment for production use

---

**Status**: All 12 initiatives completed ✅  
**Ready for**: Development continuation and production deployment
