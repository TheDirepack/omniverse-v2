#!/bin/bash
set -e

echo "Omniverse V2 Setup"
echo "=================="
echo ""

GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

err() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR=""
if [ -d "$BASE_DIR/backend/.venv" ]; then
    VENV_DIR="$BASE_DIR/backend/.venv"
elif [ -d "$BASE_DIR/backend/venv" ]; then
    VENV_DIR="$BASE_DIR/backend/venv"
fi

check_python() {
    if ! command -v python3 &>/dev/null; then
        err "python3 not found. Install Python 3.10 or later."
        exit 1
    fi
    if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
        err "Python 3.10+ required, found $(python3 --version 2>&1)"
        exit 1
    fi
    if [ -n "$VENV_DIR" ] && ! "$VENV_DIR/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
        err "Existing virtual environment requires Python 3.10 or later. Remove it and rerun setup."
        exit 1
    fi
    ok "Python $(python3 --version | cut -d' ' -f2)"
}

create_venv() {
    if [ -n "$VENV_DIR" ]; then
        info "Virtual environment already exists: $VENV_DIR"
        return
    fi
    info "Creating Python virtual environment..."
    python3 -m venv "$BASE_DIR/backend/.venv"
    VENV_DIR="$BASE_DIR/backend/.venv"
    ok "Virtual environment created at backend/.venv"
}

install_deps() {
    info "Installing dependencies..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -q -r "$BASE_DIR/backend/requirements.txt"
    if [ -f "$BASE_DIR/backend/requirements-dev.txt" ]; then
        "$VENV_DIR/bin/pip" install -q -r "$BASE_DIR/backend/requirements-dev.txt"
        ok "Development dependencies installed"
    fi
    ok "Dependencies installed"
}

setup_env() {
    mkdir -p "$BASE_DIR/backend/data/v2-blobs" "$BASE_DIR/backend/data/v2-secrets"
    if [ ! -f "$BASE_DIR/backend/.env.local" ]; then
        warn "No .env.local found. Creating minimal configuration..."
        cat > "$BASE_DIR/backend/.env.local" << 'EOF'
# Omniverse V2 - Local Development Settings
OMNIVERSE_V2_DATABASE_PATH=./data/omniverse-v2.db
OMNIVERSE_V2_BLOB_PATH=./data/v2-blobs
OMNIVERSE_V2_CREDENTIALS_PATH=./data/v2-secrets/credentials.json
OMNIVERSE_V2_BIND_HOST=127.0.0.1
OMNIVERSE_V2_REQUIRE_LOOPBACK=true
EOF
        ok "Created backend/.env.local with defaults"
    else
        ok ".env.local exists"
    fi
}

check_python
create_venv
install_deps
setup_env

echo ""
ok "Setup complete!"
echo "Run './run.sh' to start the application."
