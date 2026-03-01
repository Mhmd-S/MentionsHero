#!/bin/sh

# Trap SIGTERM/SIGINT to cleanly shut down both processes
cleanup() {
  echo "Shutting down..."
  kill "$FASTAPI_PID" 2>/dev/null
  exit 0
}
trap cleanup SIGTERM SIGINT

# Start FastAPI in background
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 &
FASTAPI_PID=$!

# Wait for FastAPI to be ready
echo "Waiting for FastAPI to start..."
for i in $(seq 1 30); do
  if kill -0 "$FASTAPI_PID" 2>/dev/null && \
     python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" 2>/dev/null; then
    echo "FastAPI is ready"
    break
  fi
  sleep 1
done

# Start Nuxt in foreground (container exits if this dies)
exec node .output/server/index.mjs
