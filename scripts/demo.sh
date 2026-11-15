#!/usr/bin/env bash
# One command for the demo.
#
#   scripts/demo.sh            live API (if .env has TIGER_DATABASE_URL) + web, models in mock mode
#   LIVE=1 scripts/demo.sh     the same, with LLM_MODE=live (real model calls; needs ~/.stormscore/caps.json)
#   WEB_PORT=5174 scripts/demo.sh   another web port (the API stays on :8000, where the Vite proxy looks)
#
# Works from any checkout whose root has a .env (a symlink is fine). Ctrl+C stops everything
# this script started. The .env is only tested for a key's presence; its values are never printed.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
API_PORT=8000
WEB_PORT="${WEB_PORT:-5173}"
PYTHON="${PYTHON:-$HOME/.venvs/stormscore/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3 || true)"

die() { echo "demo: $*" >&2; exit 1; }
port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

command -v node >/dev/null || die "node is not installed (the web app needs it)"
[ -n "$PYTHON" ] || die "no Python found; set PYTHON=/path/to/python"
port_busy "$WEB_PORT" && die "port $WEB_PORT is already in use; stop the other server first"

# Is there a Tiger URL in .env? Presence only: the value stays unread by this script's output.
HAVE_TIGER=0
if [ -f "$ENV_FILE" ] && grep -Eq '^[[:space:]]*(export[[:space:]]+)?TIGER_DATABASE_URL=[^[:space:]]+' "$ENV_FILE"; then
  HAVE_TIGER=1
fi

PIDS=()
cleanup() {
  local rc=$?
  trap - INT TERM EXIT
  echo
  echo "demo: stopping..."
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null
  done
  wait 2>/dev/null
  exit "$rc"
}
trap 'exit 0' INT TERM   # Ctrl+C is a normal way to finish; the EXIT trap does the stopping
trap cleanup EXIT

if [ "${LIVE:-0}" = "1" ]; then
  export LLM_MODE=live
  MODE="live models (LLM_MODE=live)"
else
  export LLM_MODE="${LLM_MODE:-mock}"
  MODE="mock models (LIVE=1 for real calls)"
fi
export STORM_ENV_FILE="$ENV_FILE"

API_NOTE="off: no TIGER_DATABASE_URL in $ENV_FILE (the web app plays the bundles as they are)"
if [ "$HAVE_TIGER" = "1" ]; then
  port_busy "$API_PORT" && die "port $API_PORT is already in use; stop the other server first"
  (cd "$ROOT/backend" && exec "$PYTHON" -m uvicorn storm.live.api:app --port "$API_PORT" --log-level warning) &
  PIDS+=("$!")
  # wait for /api/health (up to 30 s); /api/health reports tiger:false rather than failing
  for _ in $(seq 1 60); do
    curl -fs "http://localhost:$API_PORT/api/health" >/dev/null 2>&1 && break
    kill -0 "${PIDS[0]}" 2>/dev/null || die "the live API exited; run it by hand to see why: cd backend && $PYTHON -m uvicorn storm.live.api:app --port $API_PORT"
    sleep 0.5
  done
  API_NOTE="on  http://localhost:$API_PORT/api/health"
fi

# Web dev server. Call vite directly so Ctrl+C reaches it (an npm wrapper can leave it running).
# Install when node_modules is missing, or older than package-lock.json (a pull that added a dependency leaves
# vite in place but the new package out: the app then fails to build with "could not be resolved").
if [ ! -x "$ROOT/web/node_modules/.bin/vite" ] || [ "$ROOT/web/package-lock.json" -nt "$ROOT/web/node_modules/.package-lock.json" ]; then
  echo "demo: installing web dependencies (first run, or package-lock.json changed)..."
  (cd "$ROOT/web" && npm ci --no-audit --no-fund) || die "npm ci failed"
fi
(cd "$ROOT/web" && exec ./node_modules/.bin/vite --port "$WEB_PORT" --strictPort) &
PIDS+=("$!")

BUNDLES="no (only the committed mock storm will play; build them with the backend, see README)"
[ -f "$ROOT/web/public/bundles/index.json" ] && BUNDLES="yes"

cat <<MSG

  StormScore demo
    live API : $API_NOTE
    models   : $MODE
    bundles  : $BUNDLES

  Open  http://localhost:$WEB_PORT/
  (add ?storm=usdjpy-2026-07-30 for the 30 July storm)   Ctrl+C stops everything.

MSG
wait
