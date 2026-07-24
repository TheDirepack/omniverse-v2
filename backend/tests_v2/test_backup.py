from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.v2 import backup
from app.v2.db import (
    bootstrap_schema,
    create_sqlite_engine,
    validate_initialized_schema,
)


def test_online_backup_restores_complete_wal_database(
    isolated_paths: dict[str, Path], tmp_path: Path
) -> None:
    database = isolated_paths["database"]
    engine = create_sqlite_engine(database)
    bootstrap_schema(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source (id, canonical_url, source_class) "
                "VALUES ('wal-row', 'https://example.invalid/wal', 'SECONDARY')"
            )
        )
    assert Path(f"{database}-wal").exists()

    backup_path = backup.create_online_backup(engine, tmp_path / "backup.db")
    restored_path = backup.restore_backup(backup_path, tmp_path / "restored.db")
    restored = create_sqlite_engine(restored_path)

    validate_initialized_schema(restored, require_seed=False)
    with restored.connect() as connection:
        assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        assert (
            connection.execute(
                text("SELECT canonical_url FROM source WHERE id = 'wal-row'")
            ).scalar_one()
            == "https://example.invalid/wal"
        )
