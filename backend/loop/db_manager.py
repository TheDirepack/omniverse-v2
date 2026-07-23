import json
import shutil
import sqlite3
from pathlib import Path

from loop.loop_config import DATA_DIR, BACKUP_DIR, LOOP_BACKUP_DIR, DBS


def ensure_dirs():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOOP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_dbs(tag: str = "pre_loop"):
    ensure_dirs()
    snap_dir = LOOP_BACKUP_DIR / tag
    snap_dir.mkdir(parents=True, exist_ok=True)
    for name, path in DBS.items():
        if path.exists():
            shutil.copy2(path, snap_dir / f"{name}.db")
    return snap_dir


def backup_settings():
    ensure_dirs()
    if DBS["settings"].exists():
        shutil.copy2(DBS["settings"], BACKUP_DIR / "settings.db.bak")


def restore_settings():
    ensure_dirs()
    bak = BACKUP_DIR / "settings.db.bak"
    if bak.exists():
        shutil.copy2(bak, DBS["settings"])
        return True
    return False


def delete_all_dbs(exclude_settings: bool = True):
    for name, path in DBS.items():
        if exclude_settings and name == "settings":
            continue
        if path.exists():
            path.unlink()


def delete_agent_log():
    log_path = DBS["settings"].parent.parent / "logs" / "agents.log"
    if log_path.exists():
        log_path.write_text("", encoding="utf-8")


def reset_to_clean_state():
    backup_settings()
    delete_all_dbs(exclude_settings=True)
    restore_settings()
    delete_agent_log()


def restore_loop_snapshot(tag: str):
    snap_dir = LOOP_BACKUP_DIR / tag
    if not snap_dir.exists():
        return False
    for name, path in DBS.items():
        snap_file = snap_dir / f"{name}.db"
        if snap_file.exists():
            shutil.copy2(snap_file, path)
    return True


def get_all_db_sizes() -> dict[str, int]:
    sizes = {}
    for name, path in DBS.items():
        if path.exists():
            sizes[name] = path.stat().st_size
    return sizes


def get_notebook_artifact_count() -> int:
    path = DBS["notebook"]
    if not path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM acquisitionartifact")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_main_db_artifact_count() -> int:
    path = DBS["main"]
    if not path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM artifact")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_world_count() -> int:
    path = DBS["main"]
    if not path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM universe")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0
