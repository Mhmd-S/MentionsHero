#!/bin/sh

# Start FastAPI in background
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 &

# Start Nuxt in foreground (container exits if this dies)
exec node .output/server/index.mjs
