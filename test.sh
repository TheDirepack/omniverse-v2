#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR=""
if [ -d "$BASE_DIR/backend/.venv" ]; then
    VENV_DIR="$BASE_DIR/backend/.venv"
elif [ -d "$BASE_DIR/backend/venv" ]; then
    VENV_DIR="$BASE_DIR/backend/venv"
else
    echo "[ERROR] Virtual environment not found. Run ./setup.sh first." >&2
    exit 1
fi

export PYTHONPATH="$BASE_DIR/backend:$PYTHONPATH"
PYTHON_EXE="$VENV_DIR/bin/python"
PYTEST_ARGS=()
TARGET="backend/tests_v2"
RUN_SLOW=false
RUN_EVALUATION=false
HAS_PATH=false

for arg in "$@"; do
    case "$arg" in
        --ui) TARGET="backend/tests_v2/ui" ;;
        --slow) RUN_SLOW=true ;;
        --evaluation) RUN_EVALUATION=true ;;
        backend/tests_v2*|tests_v2*)
            PYTEST_ARGS+=("$arg")
            HAS_PATH=true
            ;;
        *) PYTEST_ARGS+=("$arg") ;;
    esac
done

if $HAS_PATH; then
    TARGET=""
fi

MARKER="not network and not slow and not evaluation"
if $RUN_SLOW; then
    MARKER="not network and not evaluation"
fi
if $RUN_EVALUATION; then
    MARKER="not network"
fi

echo "[INFO] Running v2 tests..."
if [ -n "$TARGET" ]; then
    "$PYTHON_EXE" -m pytest -c "$BASE_DIR/backend/pytest-v2.ini" "$TARGET" -v --tb=short -m "$MARKER" "${PYTEST_ARGS[@]}"
else
    "$PYTHON_EXE" -m pytest -c "$BASE_DIR/backend/pytest-v2.ini" -v --tb=short -m "$MARKER" "${PYTEST_ARGS[@]}"
fi
echo "[OK] Tests passed."
