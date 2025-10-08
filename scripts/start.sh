#!/usr/bin/env bash
set -euo pipefail

# Run FastAPI backend and Vite frontend concurrently
PY=${PYTHON:-python3}
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

cd "$ROOT_DIR"

# Activate local venv if present
if [ -d "$ROOT_DIR/.venv" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

# Ensure backend can import the app package
export PYTHONPATH="${PYTHONPATH:-}:$ROOT_DIR/agentic-stock-research"

# Start backend
$PY -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACK_PID=$!

# Start frontend
cd "$ROOT_DIR/agentic-stock-research/frontend"
npm run dev &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID' INT TERM EXIT

wait
