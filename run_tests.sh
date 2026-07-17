#!/bin/bash

set -e

cd "$(dirname "$0")"

# Activate virtual environment and run tests
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
elif [ -d "backend/venv" ]; then
    source backend/venv/bin/activate
else
    echo "Error: Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

export PYTHONPATH=./backend:$PYTHONPATH

echo "=== Running All Tests ==="
pytest backend/tests/ -v --asyncio-mode=auto -x
