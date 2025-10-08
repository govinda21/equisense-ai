#!/usr/bin/env bash
set -euo pipefail

# Concurrent dev runner for backend (FastAPI) and frontend (Vite)
# Usage: ./scripts/dev.sh

# Resolve repo root as the parent of this scripts directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BACKEND_DIR="${REPO_ROOT}/agentic-stock-research"
FRONTEND_DIR="${BACKEND_DIR}/frontend"

# Prefer existing virtualenv at repo root
if [[ -f "${REPO_ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.venv/bin/activate"
fi

# Default ports
export API_PORT="${API_PORT:-8000}"

# Ensure frontend .env has API base URL
mkdir -p "${FRONTEND_DIR}"
if [[ ! -f "${FRONTEND_DIR}/.env" ]]; then
  printf "VITE_API_BASE_URL=http://localhost:%s\n" "${API_PORT}" > "${FRONTEND_DIR}/.env"
fi

pids=()

start_backend() {
  echo "[dev] Starting backend on http://localhost:${API_PORT}"
  (
    cd "${BACKEND_DIR}" && \
    uvicorn app.main:app --reload --port "${API_PORT}" --log-level info
  ) &
  pids+=("$!")
}

start_frontend() {
  echo "[dev] Ensuring frontend deps..."
  (
    cd "${FRONTEND_DIR}" && \
    if [[ ! -d node_modules ]]; then npm install --silent; fi
  )

  echo "[dev] Starting frontend (Vite)"
  (
    cd "${FRONTEND_DIR}" && \
    npm run dev -- --host
  ) &
  pids+=("$!")
}

cleanup() {
  echo "[dev] Shutting down..."
  for pid in "${pids[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup EXIT INT TERM

start_backend
start_frontend

echo "[dev] Tailing processes. Press Ctrl+C to stop."
wait -n || true
wait || true


