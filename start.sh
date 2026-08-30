#!/bin/sh
# Runs FastAPI (:8001) and Nuxt (:$PORT) in one container.
#
# Both processes are supervised: if either exits, the whole container exits
# non-zero so the platform restarts it. Letting Nuxt outlive FastAPI produces a
# site that serves every page fine while every /api/** request 502s — and it
# passes any health check that only hits /.

set -u

FASTAPI_PID=""
NUXT_PID=""

cleanup() {
  echo "Shutting down..."
  [ -n "$NUXT_PID" ] && kill "$NUXT_PID" 2>/dev/null
  [ -n "$FASTAPI_PID" ] && kill "$FASTAPI_PID" 2>/dev/null
  exit 0
}
trap cleanup TERM INT

# Start FastAPI in background
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 &
FASTAPI_PID=$!

# Wait for FastAPI to be ready
echo "Waiting for FastAPI to start..."
READY=0
i=1
while [ "$i" -le 30 ]; do
  if ! kill -0 "$FASTAPI_PID" 2>/dev/null; then
    echo "FastAPI exited during startup — check the traceback above"
    exit 1
  fi
  if python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" 2>/dev/null; then
    echo "FastAPI is ready"
    READY=1
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$READY" -eq 0 ]; then
  echo "FastAPI did not answer /health within 30s — starting Nuxt anyway"
fi

# Nuxt reads its Supabase config from `runtimeConfig.public.supabase.{url,key}`,
# which Nuxt only overrides from the env names derived from that path:
# NUXT_PUBLIC_SUPABASE_URL / NUXT_PUBLIC_SUPABASE_KEY. The platform supplies
# SUPABASE_URL / SUPABASE_KEY (what FastAPI reads), and the image has no .env
# (.dockerignore excludes it) and no build ARGs, so nothing is baked in at build
# time either. Without this mapping every server-rendered page returns
# "Your project's URL and Key are required to create a Supabase client!" while the
# static routes (/rss.xml, /sitemap.xml, /_nuxt_icon) keep returning 200 — a total
# outage that never reproduces locally, because a local build always has .env.
#
# This must happen before node starts: Nuxt applies env overrides while building its
# runtime config, and that config is frozen by the time any Nitro plugin could run.
export NUXT_PUBLIC_SUPABASE_URL="${NUXT_PUBLIC_SUPABASE_URL:-${SUPABASE_URL:-}}"
export NUXT_PUBLIC_SUPABASE_KEY="${NUXT_PUBLIC_SUPABASE_KEY:-${SUPABASE_KEY:-}}"

if [ -z "$NUXT_PUBLIC_SUPABASE_URL" ] || [ -z "$NUXT_PUBLIC_SUPABASE_KEY" ]; then
  echo "FATAL: SUPABASE_URL/SUPABASE_KEY are not set — every Nuxt page would 500."
  echo "       Set them on the service and redeploy."
  kill "$FASTAPI_PID" 2>/dev/null
  exit 1
fi

# Start Nuxt in background so we can supervise both
node .output/server/index.mjs &
NUXT_PID=$!

while true; do
  if ! kill -0 "$FASTAPI_PID" 2>/dev/null; then
    echo "FastAPI exited — stopping container so it gets restarted"
    kill "$NUXT_PID" 2>/dev/null
    exit 1
  fi
  if ! kill -0 "$NUXT_PID" 2>/dev/null; then
    echo "Nuxt exited — stopping container so it gets restarted"
    kill "$FASTAPI_PID" 2>/dev/null
    exit 1
  fi
  sleep 2
done
