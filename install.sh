#!/usr/bin/env bash
#
# briarPipe onboarding — opens the setup form in your browser so you can generate
# a config.yml without touching YAML.
#
#   curl -fsSL https://raw.githubusercontent.com/lubabs770/briarPipe/main/install.sh | bash
#
# It serves form/index.html on a local port and opens it. Nothing is installed
# system-wide; press Ctrl-C when you're done.

set -euo pipefail

RAW_BASE="${BRIARPIPE_RAW_BASE:-https://raw.githubusercontent.com/lubabs770/briarPipe/main}"
PORT="${BRIARPIPE_PORT:-8773}"

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "briarPipe: Python 3 is required to serve the form." >&2
  exit 1
fi

# Use a local checkout's form if we're inside the repo; otherwise download it.
if [ -f "form/index.html" ]; then
  SERVE_DIR="form"
  CLEANUP=""
else
  SERVE_DIR="$(mktemp -d)"
  CLEANUP="$SERVE_DIR"
  echo "briarPipe: fetching the setup form…"
  curl -fsSL "$RAW_BASE/form/index.html" -o "$SERVE_DIR/index.html"
fi

cleanup() {
  [ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null || true
  [ -n "$CLEANUP" ] && rm -rf "$CLEANUP" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Find a free port starting at $PORT. Exit 0 == free (nothing listening).
is_free() { "$PY" -c "import socket,sys; \
r=socket.socket().connect_ex(('127.0.0.1', int(sys.argv[1]))); \
sys.exit(0 if r != 0 else 1)" "$1" 2>/dev/null; }
for _ in 1 2 3 4 5; do
  if is_free "$PORT"; then break; fi
  PORT=$((PORT + 1))
done

( cd "$SERVE_DIR" && exec "$PY" -m http.server "$PORT" >/dev/null 2>&1 ) &
SRV_PID=$!
sleep 1

URL="http://localhost:$PORT/index.html"
echo "briarPipe: setup form running at $URL"
echo "Fill it in, save the result as config.yml in your repo, and commit it."
echo "Press Ctrl-C to stop."

if command -v open >/dev/null 2>&1; then open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
else echo "Open this in your browser: $URL"; fi

wait "$SRV_PID"
