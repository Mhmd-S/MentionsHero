#!/bin/bash

# Start backend (FastAPI)
osascript -e 'tell application "Terminal" to do script "cd /Users/moslmn/projects/transcripts_generator && source backend/venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload --reload-delay 2"'

# Start frontend (Nuxt)
osascript -e 'tell application "Terminal" to do script "cd /Users/moslmn/projects/transcripts_generator && npm run dev"'

echo "Dev servers starting in separate Terminal windows..."
echo "  Backend: http://localhost:8001"
echo "  Frontend: http://localhost:3000"