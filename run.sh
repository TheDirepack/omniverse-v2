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
else
    echo "ERROR: No virtual environment found. Run './setup.sh' first."
    exit 1
fi

if [ -n "$VIRTUAL_ENV" ]; then
    venv_uvicorn="$VIRTUAL_ENV/bin/uvicorn"
    if command -v "$venv_uvicorn" &> /dev/null; then
        "$venv_uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
    else
        echo "ERROR: uvicorn not found in venv."
        exit 1
    fi
else
    echo "ERROR: No virtual environment active. Run './setup.sh' first."
    exit 1
fi
