from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.v2.db import (
    SchemaValidationError,
    bootstrap_schema,
    create_sqlite_engine,
    validate_initialized_schema,
)


def _alembic_config(database: Path) -> Config:
    backend = Path(__file__).parents[1]
    config = Config(backend / "alembic-v2.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    return config


@pytest.mark.integration
def test_bootstrap_schema_migrates_to_exact_head(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)

    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert revision == "v2_0002_freshness_scope"
    tables = set(inspect(engine).get_table_names())
    assert not any("tier" in table or "theory" in table for table in tables)
    assert "power_profile" not in tables


@pytest.mark.integration
def test_migration_downgrade_to_base_and_reupgrade(
    isolated_paths: dict[str, Path],
) -> None:
    config = _alembic_config(isolated_paths["database"])
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    engine = create_sqlite_engine(isolated_paths["database"])
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}

    command.upgrade(config, "head")
    validate_initialized_schema(engine, require_seed=False)


@pytest.mark.integration
def test_schema_validation_rejects_outdated_revision(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE alembic_version SET version_num = 'outdated_revision'")
        )

    with pytest.raises(SchemaValidationError, match="alembic upgrade head"):
        validate_initialized_schema(engine, require_seed=False)


@pytest.mark.integration
def test_schema_validation_rejects_missing_column(
    isolated_paths: dict[str, Path],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE provider DROP COLUMN base_url"))

    with pytest.raises(SchemaValidationError, match=r"provider\.base_url"):
        validate_initialized_schema(engine, require_seed=False)
