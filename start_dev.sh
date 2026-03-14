#!/bin/bash
cd "$(dirname "$0")"
export EDITOR="code"

npx concurrently -n backend,frontend -c blue,green \
  "source backend/venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload --reload-delay 2" \
  "pnpm run dev"
