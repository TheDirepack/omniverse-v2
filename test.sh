#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Initializing Test Environment ==="
if [ ! -d "$BASE_DIR/backend/.venv" ] && [ ! -d "$BASE_DIR/backend/venv" ]; then
    echo "Error: Backend virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

if [ -d "$BASE_DIR/backend/.venv" ]; then
    VENV_PATH="$BASE_DIR/backend/.venv"
else
    VENV_PATH="$BASE_DIR/backend/venv"
fi

PYTHON_EXE="$VENV_PATH/bin/python"

echo "=== Running Backend Tests ==="
TEST_MARKER="not slow"
if [[ "$*" == *"--slow"* ]]; then
    TEST_MARKER="slow"
fi

CLEAN_ARGS=$(echo "$@" | sed 's/--slow//g')

# Run pytest from the root, targeting the backend/tests directory
$PYTHON_EXE -m pytest backend/tests/ -v --tb=short -m "$TEST_MARKER" $CLEAN_ARGS

echo ""
echo "=== Running Backend Linting/Typechecking ==="
ruff check backend
if [[ "$*" == *"--slow"* ]]; then
    mypy backend
    bandit -r backend
    pylint backend
fi

echo ""
echo "=== Running Frontend Tests ==="
cd "$BASE_DIR/frontend"
if [ -d "node_modules" ]; then
    npx vitest run
else
    echo "Skipping frontend tests: node_modules not found. Run npm install in frontend/."
fi

echo ""
echo "=== Running Frontend Linting/Typechecking ==="
npx biome check .
if [[ "$*" == *"--slow"* ]]; then
    npx tsc --noEmit
fi

echo ""
echo "=== Cleaning Up ==="
rm -f /tmp/omniverse_test.db /tmp/omniverse_test_unconfirmed.db /tmp/omniverse_test_extrapolation.db /tmp/omniverse_test_settings.db

echo "✅ Tests completed."
