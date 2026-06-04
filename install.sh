#!/usr/bin/env bash
#
# briarPipe onboarding — clones the repo into your home directory and opens the
# setup form so you can generate a config.yml without touching YAML.
#
#   curl -fsSL https://raw.githubusercontent.com/lubabs770/briarPipe/main/install.sh | bash
#
# It clones into ~/briarPipe (override with $BRIARPIPE_HOME), then serves
# form/index.html on a local port and opens it. The server stops when you press
# Ctrl-C; the clone stays so you can commit your config and push.

set -euo pipefail

REPO_URL="${BRIARPIPE_REPO:-https://github.com/lubabs770/briarPipe.git}"
DEST="${BRIARPIPE_HOME:-$HOME/briarPipe}"
PORT="${BRIARPIPE_PORT:-8773}"

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "briarPipe: Python 3 is required to serve the form." >&2
  exit 1
fi

# Acquire the repo. If we're already inside a checkout, use it in place;
# otherwise clone (or reuse an existing clone) at $DEST.
if [ -f "form/index.html" ]; then
  REPO_DIR="$(pwd)"
elif [ -d "$DEST/.git" ]; then
  echo "briarPipe: found existing clone at $DEST — updating…"
  git -C "$DEST" pull --ff-only --quiet || echo "briarPipe: couldn't update; using the clone as-is."
  REPO_DIR="$DEST"
else
  if ! command -v git >/dev/null 2>&1; then
    echo "briarPipe: git is required to clone the repo." >&2
    exit 1
  fi
  echo "briarPipe: cloning into $DEST …"
  git clone --quiet "$REPO_URL" "$DEST"
  REPO_DIR="$DEST"
fi

SERVE_DIR="$REPO_DIR/form"
if [ ! -f "$SERVE_DIR/index.html" ]; then
  echo "briarPipe: setup form not found at $SERVE_DIR/index.html." >&2
  exit 1
fi

cleanup() {
  [ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null || true
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
echo "briarPipe: cloned to $REPO_DIR"
echo "briarPipe: setup form running at $URL"
echo "Fill it in, save the result as config.yml in $REPO_DIR, then commit and push."
echo "Press Ctrl-C to stop the form server."

if command -v open >/dev/null 2>&1; then open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
else echo "Open this in your browser: $URL"; fi

wait "$SRV_PID"
