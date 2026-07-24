# Initialization refusal diagnostics are operator-facing and intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.v2.bootstrap import SeedResult, bootstrap_fresh_database
from app.v2.config import V2Config
from app.v2.db import (
    SchemaValidationError,
    bootstrap_schema,
    create_sqlite_engine,
    validate_initialized_schema,
)


def _ensure_database_is_safe(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
    except sqlite3.DatabaseError as error:
        raise SchemaValidationError(
            "refusing unrecognized non-empty database"
        ) from error
    if tables and "seed_run" not in tables:
        raise SchemaValidationError("refusing unrecognized non-empty database")


def initialize(config: V2Config) -> SeedResult:
    config.validate()
    _ensure_database_is_safe(config.database_path)
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    config.blob_path.mkdir(parents=True, exist_ok=True)
    config.credentials_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = create_sqlite_engine(
        config.database_path, busy_timeout_ms=config.sqlite_busy_timeout_ms
    )
    try:
        bootstrap_schema(engine)
        result = bootstrap_fresh_database(engine, config.seed_path)
        validate_initialized_schema(engine, seed_path=config.seed_path)
        return result
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the Omniverse v2 runtime")
    parser.parse_args()
    result = initialize(V2Config.from_env())
    print(f"initialized v2 database; imported {result.imported_count} worlds")


if __name__ == "__main__":
    main()
