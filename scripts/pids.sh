#!/usr/bin/env bash
set -euo pipefail

# Human-readable process status for Backend & Frontend
# - prints a neat table with header, timestamp and truncated commands
# - uses lsof (preferred) or ss as fallback; pgrep fallback for pattern matches

# ---- Configuration ----
CMD_TRUNC=80   # max characters of command to display
NOW_FMT="%Y-%m-%d %H:%M:%S %Z"

# ---- Tool detection ----
if command -v lsof >/dev/null 2>&1; then
  _get_pid_by_port() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN -Fp 2>/dev/null | sed -n 's/^p//p' | head -n1 || true
  }
elif command -v ss >/dev/null 2>&1; then
  _get_pid_by_port() {
    ss -ltnp "( sport = :$1 )" 2>/dev/null \
      | awk -F',' '/users:/ {
          if (match($0, /pid=[0-9]+/)) {
            pid = substr($0, RSTART+4, RLENGTH-4);
            print pid;
            exit
          }
        }'
  }
else
  _get_pid_by_port() { :; }  # no-op; will rely on pgrep fallback
fi

_get_cmd() {
  ps -o command= -p "$1" 2>/dev/null || echo ""
}

_truncate() {
  local s=${1:-}
  local n=${2:-$CMD_TRUNC}
  if [[ ${#s} -le $n ]]; then
    printf "%s" "$s"
  else
    # safe truncation; add ellipsis
    printf "%s" "${s:0:((n-1))}…"
  fi
}

# Print header
_now=$(date +"$NOW_FMT")
printf "Process status (as of %s)\n" "$_now"
printf "%-36s | %-10s | %-7s | %-6s | %s\n" "ROLE" "STATUS" "PID" "PORT" "COMMAND"
printf '%s\n' "-------------------------------------+------------+---------+--------+--------------------------------------------------------------------------------"

# role, port, fallback-pattern
report_process() {
  local role=$1 port=$2 pattern=$3 pid cmd status display_cmd
  pid=$(_get_pid_by_port "$port")
  if [[ -n "${pid:-}" ]]; then
    cmd=$(_get_cmd "$pid")
    status="Running"
    display_cmd=$(_truncate "$cmd")
    printf "%-36s | %-10s | %-7s | %-6s | %s\n" "$role" "$status" "$pid" "$port" "$display_cmd"
    return
  fi

  # port lookup failed: try pattern-based lookup (useful if non-default port)
  pid=$(pgrep -f -- "${pattern}" 2>/dev/null | head -n1 || true)
  if [[ -n "${pid:-}" ]]; then
    cmd=$(_get_cmd "$pid")
    status="Running"
    display_cmd=$(_truncate "$cmd")
    # port unknown in this case
    printf "%-36s | %-10s | %-7s | %-6s | %s\n" "$role" "$status" "$pid" "unknown" "$display_cmd"
  else
    status="Not running"
    printf "%-36s | %-10s | %-7s | %-6s | %s\n" "$role" "$status" "-" "$port" "-"
  fi
}

report_process "Backend (FastAPI / Uvicorn)" 8000 "uvicorn|fastapi|gunicorn"
report_process "Frontend (Vite / npm dev)" 5173 "vite|npm run dev|pnpm dev|npm start|node .*vite"

exit 0
