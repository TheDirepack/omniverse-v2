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

source "$VENV_DIR/bin/activate"
export PYTHONPATH="$BASE_DIR/backend:$PYTHONPATH"

if [ -f "$BASE_DIR/backend/.env.local" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$BASE_DIR/backend/.env.local"
    set +a
fi

for path_var in OMNIVERSE_V2_DATABASE_PATH OMNIVERSE_V2_BLOB_PATH OMNIVERSE_V2_CREDENTIALS_PATH; do
    path_value="${!path_var:-}"
    if [ -n "$path_value" ] && [[ "$path_value" != /* ]]; then
        printf -v "$path_var" '%s/%s' "$BASE_DIR/backend" "${path_value#./}"
        export "$path_var"
    fi
done

HOST="${OMNIVERSE_V2_BIND_HOST:-${HOST:-127.0.0.1}}"
PORT="${PORT:-8000}"
RELOAD="--reload"
MODE="dev"
APP_LOG_LEVEL=""
APP_LOG_DIR=""
APP_LOG_FILE=""

for arg in "$@"; do
    case "$arg" in
        --prod|--no-reload) RELOAD="" ; MODE="prod" ;;
        --port=*) PORT="${arg#*=}" ;;
        --host=*) HOST="${arg#*=}" ;;
        --log-level=*) APP_LOG_LEVEL="${arg#*=}" ;;
        --log-dir=*) APP_LOG_DIR="${arg#*=}" ;;
        --log-file=*) APP_LOG_FILE="${arg#*=}" ;;
        --help)
            echo "Usage: ./run.sh [OPTIONS]"
            echo ""
            echo "  --prod              Disable hot reload (production mode)"
            echo "  --host=HOST         Bind address (default: 127.0.0.1)"
            echo "  --port=PORT         Port (default: 8000)"
            echo "  --log-level=LEVEL   Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)"
            echo "  --log-dir=DIR       Directory for agent log file (default: backend/logs)"
            echo "  --log-file=FILE     Full path to agent log file (overrides --log-dir)"
            exit 0
            ;;
    esac
done

export OMNIVERSE_V2_BIND_HOST="$HOST"
case "${OMNIVERSE_V2_REQUIRE_LOOPBACK:-true}" in
    1|true|TRUE|yes|YES|on|ON)
        case "$HOST" in
            127.0.0.1|::1|localhost) ;;
            *) err "Loopback-only mode rejects public bind host: $HOST"; exit 1 ;;
        esac
        ;;
esac

export APP_LOG_LEVEL APP_LOG_DIR APP_LOG_FILE

# Check if port is in use
if command -v ss &>/dev/null; then
    if ss -tlnp "sport = :$PORT" 2>/dev/null | grep -q LISTEN; then
        warn "Port $PORT is already in use"
    fi
elif command -v lsof &>/dev/null; then
    if lsof -i :$PORT -s TCP:LISTEN 2>/dev/null | grep -q .; then
        warn "Port $PORT is already in use"
    fi
fi

info "Starting Omniverse V2 Backend (mode: $MODE, $HOST:$PORT)..."
python -m app.v2.initialize
uvicorn app.main:app --app-dir "$BASE_DIR/backend" --host "$HOST" --port "$PORT" $RELOAD
