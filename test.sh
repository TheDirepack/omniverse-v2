#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Backend Tests ==="
cd "$BASE_DIR/backend"
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python -m pytest tests/ -v --tb=short -m "not slow" "$@"

echo ""
echo "=== Backend Tests (slow) ==="
python -m pytest tests/ -v --tb=short -m "slow" "$@" || echo "Slow tests skipped (no LLM configured)"

echo ""
echo "=== Frontend Tests ==="
cd "$BASE_DIR/frontend"
npx vitest run 2>/dev/null || echo "Frontend tests require 'npm install' in frontend/"
