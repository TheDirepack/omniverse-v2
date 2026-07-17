#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

VENV_DIR=""
if [ -d "$BASE_DIR/backend/.venv" ]; then
    VENV_DIR="$BASE_DIR/backend/.venv"
elif [ -d "$BASE_DIR/backend/venv" ]; then
    VENV_DIR="$BASE_DIR/backend/venv"
else
    err "Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

PYTHON_EXE="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON_EXE" ]; then
    err "Python interpreter not found in $VENV_DIR"
    exit 1
fi

export PYTHONPATH="$BASE_DIR/backend:$PYTHONPATH"

# Parse args: separate pytest args from flags meant for this script
PYTEST_ARGS=()
RUN_UI=false
RUN_SLOW=false
RUN_PROMPT=false
for arg in "$@"; do
    case "$arg" in
        --ui)       RUN_UI=true ;;
        --slow)     RUN_SLOW=true ;;
        --prompt-robustness) RUN_PROMPT=true ;;
        *)          PYTEST_ARGS+=("$arg") ;;
    esac
done

MARKER="not slow"
if $RUN_SLOW; then
    MARKER="slow"
fi

if $RUN_PROMPT; then
    info "Running prompt robustness tests..."
    "$PYTHON_EXE" -m pytest backend/tests/live/test_prompt_failure_modes.py -v --tb=short -m "slow" "${PYTEST_ARGS[@]}"
    exit 0
fi

info "Running backend tests${RUN_UI:+ (including UI E2E tests)}${RUN_SLOW:+ (including slow/LLM tests)}..."

if $RUN_UI; then
    "$PYTHON_EXE" -m pytest backend/tests/ui/ -v --tb=short "${PYTEST_ARGS[@]}"
fi

"$PYTHON_EXE" -m pytest backend/tests/ -v --tb=short -m "$MARKER" "${PYTEST_ARGS[@]}"

echo ""
ok "Tests passed."
