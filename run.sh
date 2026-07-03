#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting Omniverse V2 Backend..."
cd "$BASE_DIR/backend"
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

echo "Starting Omniverse V2 Frontend..."
cd "$BASE_DIR/frontend"
npm run dev &

FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
