#!/usr/bin/env bash
set -euo pipefail

# Run FastAPI backend and Vite frontend concurrently
PY=${PYTHON:-python3}
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

cd "$ROOT_DIR"

# Start backend
$PY -m uvicorn app.main:app --reload --port 8000 &
BACK_PID=$!

# Start frontend
cd "$ROOT_DIR/frontend"
npm run dev &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID' INT TERM EXIT

wait
