#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill processes using the required ports
echo "Cleaning up port 8000..."
fuser -k 8000/tcp 2>/dev/null || true

if [ -f "$BASE_DIR/.env.local" ]; then
    echo "Loading .env.local..."
    export $(grep -v '^#' "$BASE_DIR/.env.local" | xargs)
fi

echo "Starting Omniverse V2 Backend (HTMX)..."
cd "$BASE_DIR/backend"
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
