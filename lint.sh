#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Ruff ==="
ruff check "$BASE_DIR/backend"

if [[ "$*" == *"--strict"* ]]; then
    echo ""
    echo "=== Mypy ==="
    mypy --strict "$BASE_DIR/backend"

    echo ""
    echo "=== Bandit ==="
    bandit -r "$BASE_DIR/backend"

    echo ""
    echo "=== Pylint ==="
    pylint "$BASE_DIR/backend"
fi

echo ""
echo "✅ Lint completed."
