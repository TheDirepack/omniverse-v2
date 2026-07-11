#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="/tmp/omniverse_backup"
MAIN_DBS=("omniverse_v2.db" "unconfirmed.db" "extrapolation.db" "settings.db")
TEMP_DB_FILES=("/tmp/omniverse_test.db" "/tmp/omniverse_test_unconfirmed.db" "/tmp/omniverse_test_extrapolation.db" "/tmp/omniverse_test_settings.db")
DATA_DIR="$BASE_DIR/backend/data"

cleanup() {
    echo ""
    echo "=== Restoring Databases and Cleaning Up ==="
    # Restore main DBs
    for db in "${MAIN_DBS[@]}"; do
        if [ -f "$BACKUP_DIR/$db" ]; then
            cp "$BACKUP_DIR/$db" "$DATA_DIR/$db"
        fi
    done
    # Remove ephemeral test DBs
    rm -f "${TEMP_DB_FILES[@]}"
    rm -rf "$BACKUP_DIR"
    echo "✅ Restore and cleanup completed."
}

trap cleanup EXIT

# Backup main DBs
mkdir -p "$BACKUP_DIR" "$DATA_DIR"
for db in "${MAIN_DBS[@]}"; do
    if [ -f "$DATA_DIR/$db" ]; then
        cp "$DATA_DIR/$db" "$BACKUP_DIR/"
    fi
done

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
export PYTHONPATH=$PYTHONPATH:$BASE_DIR/backend
TEST_MARKER="not slow"
USE_PROD_SETTINGS=""
if [[ "$*" == *"--slow"* ]]; then
    TEST_MARKER="slow"
    USE_PROD_SETTINGS="USE_PROD_SETTINGS=1"
fi

CLEAN_ARGS=$(echo "$@" | sed 's/--slow//g')

# Run prompt robustness tests separately if requested
if [[ "$*" == *"--prompt-robustness"* ]]; then
    echo "=== Running Prompt Robustness Tests ==="
    CLEAN_PROMPT_ARGS=$(echo "$@" | sed 's/--prompt-robustness//g')
    env $USE_PROD_SETTINGS $PYTHON_EXE -m pytest backend/tests/live/test_prompt_failure_modes.py -v --tb=short -m "slow" $CLEAN_PROMPT_ARGS
    exit 0
fi

# Run pytest from the root, targeting the backend/tests directory
env $USE_PROD_SETTINGS $PYTHON_EXE -m pytest backend/tests/ -v --tb=short -m "$TEST_MARKER" $CLEAN_ARGS

echo ""
echo "=== Running Backend Linting/Typechecking ==="
ruff check "$BASE_DIR/backend" || echo "⚠️  Ruff found issues (many are pre-existing)"
if [[ "$*" == *"--slow"* ]]; then
    mypy --strict "$BASE_DIR/backend" || echo "⚠️  Mypy found issues"
    bandit -r "$BASE_DIR/backend" || echo "⚠️  Bandit found issues"
    pylint "$BASE_DIR/backend" || echo "⚠️  Pylint found issues"
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

echo "✅ Tests completed."
