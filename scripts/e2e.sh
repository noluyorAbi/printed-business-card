#!/usr/bin/env bash
#
# Run the end to end suite against the real stack: the Python worker in one
# process, a production build of the web app in another, Playwright driving a
# browser against both. No mocks, because the things worth catching here live
# in the seams between the three.
#
#   scripts/e2e.sh              full suite
#   scripts/e2e.sh --project=desktop -g "export"    passed through to playwright
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

WORKER_PORT="${WORKER_PORT:-8099}"
WEB_PORT="${WEB_PORT:-3111}"
export WORKER_TOKEN="${WORKER_TOKEN:-e2e-token}"
export WORKER_URL="http://127.0.0.1:${WORKER_PORT}"
# The whole suite arrives from one address, which is exactly what the rate
# limit is built to stop. Raise it here rather than weaken it in production.
export RATE_RENDER="${RATE_RENDER:-5000}"
export RATE_EXPORT="${RATE_EXPORT:-500}"

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_for() {
  local url="$1" name="$2" tries=90
  until curl -sf -o /dev/null "$url"; do
    tries=$((tries - 1))
    if [ "$tries" -le 0 ]; then
      echo "$name never came up at $url" >&2
      exit 1
    fi
    sleep 1
  done
  echo "$name is up"
}

echo "==> worker on :$WORKER_PORT"
"$PYTHON" -m uvicorn worker.app:app --host 127.0.0.1 --port "$WORKER_PORT" \
  --log-level warning &
pids+=($!)
wait_for "http://127.0.0.1:${WORKER_PORT}/health" "worker"

echo "==> web on :$WEB_PORT"
cd web
[ -d .next ] || npm run build
npx next start --port "$WEB_PORT" --hostname 127.0.0.1 > /tmp/e2e-web.log 2>&1 &
pids+=($!)
wait_for "http://127.0.0.1:${WEB_PORT}/" "web"

echo "==> playwright"
BASE_URL="http://127.0.0.1:${WEB_PORT}" npx playwright test "$@"
