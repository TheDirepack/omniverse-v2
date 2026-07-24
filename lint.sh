#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${CYAN}[WARN]${NC} $*" >&2; }

VENV_DIR=""
if [ -d "$BASE_DIR/backend/.venv" ]; then
    VENV_DIR="$BASE_DIR/backend/.venv/bin"
elif [ -d "$BASE_DIR/backend/venv" ]; then
    VENV_DIR="$BASE_DIR/backend/venv/bin"
fi

RUFF="${VENV_DIR}/ruff"
BANDIT="${VENV_DIR}/bandit"
PYLINT="${VENV_DIR}/pylint"

if [ -z "$VENV_DIR" ]; then
    err "Virtual environment not found. Run ./setup.sh first."
    exit 1
fi

if [ ! -f "$RUFF" ]; then
    err "ruff not found in venv. Run ./setup.sh to install dependencies."
    exit 1
fi

info "Ruff: checking the V2 release target..."
"$RUFF" check "$BASE_DIR/backend/app/v2" "$BASE_DIR/backend/tests_v2"

if [[ "$*" == *"--strict"* ]]; then
    echo ""
    info "Strict mode: running additional checks..."

    if [ -f "${VENV_DIR}/mypy" ]; then
        "${VENV_DIR}/mypy" "$BASE_DIR/backend/app/v2" || warn "mypy found issues"
    else
        warn "mypy not installed, skipping"
    fi

    if [ -f "$BANDIT" ]; then
        "$BANDIT" -r "$BASE_DIR/backend/app/v2" || warn "bandit found issues"
    else
        warn "bandit not installed, skipping"
    fi

    if [ -f "$PYLINT" ]; then
        "$PYLINT" "$BASE_DIR/backend/app/v2" || warn "pylint found issues"
    else
        warn "pylint not installed, skipping"
    fi
fi

echo ""
ok "Lint completed."
