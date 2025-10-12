#!/usr/bin/env bash
set -euo pipefail

# Run FastAPI backend and Vite frontend concurrently
PY=${PYTHON:-python3}
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:5173"

cd "$ROOT_DIR"

# Load Homebrew environment if available (for npm)
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Starting EquiSense AI Stock Research Platform"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Activate local venv if present
if [ -d "$ROOT_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
  echo "✓ Virtual environment activated"
fi

# Ensure backend can import the app package
export PYTHONPATH="${PYTHONPATH:-}:$ROOT_DIR/agentic-stock-research"

# Start backend
echo ""
echo "Starting Backend (FastAPI)..."
$PY -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACK_PID=$!

# Start frontend
echo "Starting Frontend (React + Vite)..."
cd "$ROOT_DIR/agentic-stock-research/frontend"
npm run dev &
FRONT_PID=$!

# Wait for services to start
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 Services Started Successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  📊 Frontend UI:  $FRONTEND_URL"
echo "  🔌 Backend API:  $BACKEND_URL"
echo "  📖 API Docs:     $BACKEND_URL/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null' INT TERM EXIT

wait
