#!/usr/bin/env bash
#
# stop.sh - gracefully stop frontend and backend services
#
# Usage:
#   ./stop.sh              # stop both services (default)
#   ./stop.sh all          # stop both services
#   ./stop.sh backend      # stop backend only
#   ./stop.sh frontend     # stop frontend only
#   ./stop.sh --help
#
# Behaviour:
#  - Attempts port-based PID detection (8000 backend, 5173 frontend).
#  - Falls back to pattern-based detection (pgrep -f) for non-standard invocations.
#  - Sends SIGTERM, waits up to TIMEOUT seconds, then SIGKILL if necessary.

set -euo pipefail

# --- Configurable parameters ---
TIMEOUT=10          # seconds to wait after SIGTERM before SIGKILL
SLEEP_INTERVAL=0.5  # poll interval while waiting for shutdown
BACKEND_PORT=8000
FRONTEND_PORT=5173
CMD_TRUNC=120

# --- Detection helpers ---
_have() { command -v "$1" >/dev/null 2>&1; }

_get_pids_by_port() {
  local port=$1
  if _have lsof; then
    # lsof prints lines starting with p<pid>
    lsof -nP -iTCP:"$port" -sTCP:LISTEN -Fp 2>/dev/null \
      | sed -n 's/^p//p' || true
    return
  fi

  if _have ss; then
    # parse possible multiple "pid=NNN" occurrences from ss users field
    ss -ltnp "( sport = :$port )" 2>/dev/null \
      | awk '
        {
          while (match($0, /pid=[0-9]+/)) {
            pid = substr($0, RSTART+4, RLENGTH-4);
            print pid;
            $0 = substr($0, RSTART + RLENGTH);
          }
        }' || true
    return
  fi

  # no tool available -> output nothing
  return
}

_get_cmd() {
  local pid=$1
  ps -o command= -p "$pid" 2>/dev/null || echo ""
}

_trim() {
  local s="${1:-}"
  local n=${2:-$CMD_TRUNC}
  if [[ ${#s} -le $n ]]; then
    printf "%s" "$s"
  else
    printf "%s… " "${s:0:((n-1))}"
  fi
}

# --- service PID resolution ---
# returns newline-separated PIDs
_pids_for_backend() {
  local pids
  pids=$(_get_pids_by_port "$BACKEND_PORT" || true)
  if [[ -n "${pids:-}" ]]; then
    printf "%s\n" "$pids"
    return
  fi
  # fallback patterns (uvicorn/fastapi/gunicorn)
  pgrep -f "uvicorn|fastapi|gunicorn" 2>/dev/null || true
}

_pids_for_frontend() {
  local pids
  pids=$(_get_pids_by_port "$FRONTEND_PORT" || true)
  if [[ -n "${pids:-}" ]]; then
    printf "%s\n" "$pids"
    return
  fi
  # fallback patterns (vite/npm/pnpm/node vite)
  pgrep -f "vite|npm run dev|pnpm dev|npm start|node .*vite" 2>/dev/null || true
}

# --- graceful kill ---
_kill_graceful() {
  local pid=$1
  local name=$2

  if ! kill -0 "$pid" 2>/dev/null; then
    printf "  ▶ PID %s (%s) already gone\n" "$pid" "$name"
    return 0
  fi

  printf "  ▶ Sending SIGTERM to PID %s (%s)\n" "$pid" "$name"
  kill "$pid" 2>/dev/null || {
    printf "    - failed to send SIGTERM to %s\n" "$pid"
    return 1
  }

  # wait loop
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( $(echo "$waited >= $TIMEOUT" | bc -l) )); then
      printf "    - PID %s did not exit after %ss, escalating to SIGKILL\n" "$pid" "$TIMEOUT"
      kill -9 "$pid" 2>/dev/null || {
        printf "      - failed to send SIGKILL to %s\n" "$pid"
        return 1
      }
      # give kernel a moment to reap
      sleep 0.2
      break
    fi
    sleep "$SLEEP_INTERVAL"
    waited=$(awk "BEGIN{print $waited + $SLEEP_INTERVAL}")
  done

  if kill -0 "$pid" 2>/dev/null; then
    printf "    - PID %s remains after escalation (unexpected)\n" "$pid"
    return 1
  fi

  printf "    - PID %s stopped\n" "$pid"
  return 0
}

# --- orchestrator ---
_stop_service() {
  local svc_name=$1
  local pid_getter=$2     # store function name as a string

  printf "%s\n" "Stopping ${svc_name}..."
  local pids raw
  raw="$($pid_getter)" || raw=""
  if [[ -z "${raw// }" ]]; then
    printf "  ▶ No %s process found\n" "$svc_name"
    return 0
  fi

  # convert newline-separated list to array of unique pids
  local pids_array=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && pids_array+=("$line")
  done < <(printf "%s\n" "$raw" | awk '!seen[$0]++' | tr -s '[:space:]' '\n')
  for pid in "${pids_array[@]}"; do
    # safety: ensure pid is integer
    if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
      printf "  ▶ Ignoring non-numeric PID: %s\n" "$pid"
      continue
    fi
    local cmd
    cmd=$(_get_cmd "$pid")
    printf "  - PID: %s  CMD: %s\n" "$pid" "$(_trim "$cmd")"
    _kill_graceful "$pid" "$svc_name" || printf "    ! warning: failed to fully stop PID %s\n" "$pid"
  done
  return 0
}

_usage() {
  cat <<EOF
Usage: $0 [backend|frontend|all]
  If no argument provided, 'all' is assumed.
  Examples:
    $0            # stop both
    $0 backend    # stop backend only
    $0 frontend   # stop frontend only
EOF
}

# --- main ---
main() {
  local target="${1:-all}"

  case "$target" in
    -h|--help|help)
      _usage
      exit 0
      ;;
    all|both|"")
      _stop_service "Backend (FastAPI/Uvicorn)" _pids_for_backend
      _stop_service "Frontend (Vite/npm dev)"   _pids_for_frontend
      ;;
    backend)
      _stop_service "Backend (FastAPI/Uvicorn)" _pids_for_backend
      ;;
    frontend)
      _stop_service "Frontend (Vite/npm dev)" _pids_for_frontend
      ;;
    *)
      printf "Unknown target: %s\n\n" "$target"
      _usage
      exit 2
      ;;
  esac

  printf "\nDone.\n"
}

main "${1:-}"
