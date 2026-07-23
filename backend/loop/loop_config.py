from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backup"
LOOP_BACKUP_DIR = DATA_DIR / "loop_snapshots"
LOGS_DIR = BASE_DIR / "logs"
AGENT_LOG_FILE = LOGS_DIR / "agents.log"

DBS = {
    "settings": DATA_DIR / "settings.db",
    "main": DATA_DIR / "omniverse_v2.db",
    "notebook": DATA_DIR / "notebook.db",
    "operational": DATA_DIR / "operational.db",
    "extrapolation": DATA_DIR / "extrapolation.db",
}

FALLOUT_NV_SLUG = "fallout_nv"

DEFAULT_WORLDS_JSON = BASE_DIR / "app" / "db" / "default_worlds.json"

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
