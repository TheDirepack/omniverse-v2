#!/bin/bash

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
elif [ -d "backend/venv" ]; then
    source backend/venv/bin/activate
else
    echo "Error: Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

export PYTHONPATH=./backend:$PYTHONPATH

# Start FastAPI server
echo "🚀 Starting Omniverse V2 Backend..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
