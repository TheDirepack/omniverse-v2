from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine


class BackupIntegrityError(RuntimeError):
    def __init__(self, result: object) -> None:
        super().__init__(f"SQLite integrity_check failed: {result!r}")


class FileBackedSQLiteRequiredError(ValueError):
    def __init__(self) -> None:
        super().__init__("online backup requires a file-backed SQLite engine")


def _validate_integrity(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise BackupIntegrityError(result)


def _sqlite_backup(source: Path, destination: Path) -> Path:
    source = Path(source)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (
            sqlite3.connect(
                f"{source.resolve().as_uri()}?mode=ro", uri=True
            ) as source_connection,
            sqlite3.connect(destination) as destination_connection,
        ):
            source_connection.backup(destination_connection)
            _validate_integrity(destination_connection)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def create_online_backup(engine: Engine, destination: Path) -> Path:
    if engine.dialect.name != "sqlite" or not engine.url.database:
        raise FileBackedSQLiteRequiredError
    return _sqlite_backup(Path(engine.url.database), destination)


def restore_backup(backup_path: Path, destination: Path) -> Path:
    return _sqlite_backup(backup_path, destination)
