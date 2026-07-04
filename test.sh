#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Backend Tests ==="
cd "$BASE_DIR"
if [ -f "backend/.venv/bin/activate" ]; then
    source backend/.venv/bin/activate
elif [ -f "backend/venv/bin/activate" ]; then
    source backend/venv/bin/activate
fi

python -m pytest tests/ -v --tb=short -m "not slow" "$@"

sleep 2  # let real_server fixture release port

echo ""
echo "=== Backend Tests (slow) ==="
python -m pytest tests/ -v --tb=short -m "slow" "$@" || echo "Slow tests skipped (no LLM configured)"

echo ""
echo "=== Frontend Tests ==="
cd "$BASE_DIR/frontend"
npx vitest run 2>/dev/null || echo "Frontend tests require 'npm install' in frontend/"
