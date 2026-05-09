#!/usr/bin/env bash
# BOF Archive — local development server
# Always serves on port 2104. Don't change.
set -euo pipefail

PORT=2104
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if lsof -ti ":$PORT" >/dev/null 2>&1; then
  echo "Port $PORT already in use. Killing existing process…"
  lsof -ti ":$PORT" | xargs kill 2>/dev/null || true
  sleep 0.3
fi

cd "$ROOT"
echo "BOF Archive → http://localhost:$PORT/"
exec python3 -m http.server "$PORT"
