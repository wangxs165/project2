#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

OVERRIDE_APP_HOST="${APP_HOST-}"
OVERRIDE_APP_PORT="${APP_PORT-}"
OVERRIDE_OPEN_BROWSER="${OPEN_BROWSER-}"
OVERRIDE_PYTHON="${PYTHON-}"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

if [[ -n "$OVERRIDE_APP_HOST" ]]; then APP_HOST="$OVERRIDE_APP_HOST"; fi
if [[ -n "$OVERRIDE_APP_PORT" ]]; then APP_PORT="$OVERRIDE_APP_PORT"; fi
if [[ -n "$OVERRIDE_OPEN_BROWSER" ]]; then OPEN_BROWSER="$OVERRIDE_OPEN_BROWSER"; fi
if [[ -n "$OVERRIDE_PYTHON" ]]; then PYTHON="$OVERRIDE_PYTHON"; fi

APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8080}"
APP_URL="http://${APP_HOST}:${APP_PORT}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"
PYTHON="${PYTHON:-.venv/bin/python}"
RUN_DIR="$PROJECT_ROOT/.run"
LOG_FILE="$RUN_DIR/project2-api.log"
PID_FILE="$RUN_DIR/project2-api.pid"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python runtime not found at $PYTHON"
  echo 'Install dependencies first: python3 -m pip install -e ".[api,yfinance]"'
  exit 1
fi

is_healthy() {
  curl --max-time 2 -fsS "$APP_URL/health" >/dev/null 2>&1
}

listener_info() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN 2>/dev/null || true
  fi
}

if is_healthy; then
  echo "Project2 API is already running at $APP_URL"
else
  LISTENER="$(listener_info)"
  if [[ -n "$LISTENER" ]]; then
    echo "Port $APP_PORT is already in use, but $APP_URL/health is not healthy."
    echo "$LISTENER"
    echo "Stop that process or set a different port, for example:"
    echo "APP_PORT=8081 ./scripts/start_app.sh"
    exit 1
  fi

  mkdir -p "$RUN_DIR"
  echo "Starting Project2 API at $APP_URL"
  APP_HOST="$APP_HOST" APP_PORT="$APP_PORT" nohup "$PYTHON" -m backend.trading_monitor.api >"$LOG_FILE" 2>&1 &
  echo "$!" >"$PID_FILE"

  for _ in {1..30}; do
    if is_healthy; then
      echo "Project2 API started with PID $(cat "$PID_FILE")"
      break
    fi
    sleep 1
  done

  if ! is_healthy; then
    echo "Project2 API did not become healthy. Last log lines:"
    tail -n 40 "$LOG_FILE" || true
    exit 1
  fi
fi

if [[ "$OPEN_BROWSER" != "0" ]]; then
  if command -v open >/dev/null 2>&1; then
    open -a "Google Chrome" "$APP_URL" || open "$APP_URL"
  else
    echo "Open this URL in your browser: $APP_URL"
  fi
fi

echo "Dashboard: $APP_URL"
echo "Log file: $LOG_FILE"
