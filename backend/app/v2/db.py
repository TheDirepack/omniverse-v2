# Schema validation diagnostics are operator-facing and intentionally explicit.
# ruff: noqa: TRY003

from __future__ import annotations

import hashlib
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session

from app.v2.models import (
    AuditDecisionRecord,
    Base,
    CanonNodeRevision,
    ContextManifest,
    EvidenceFragment,
    IntegrationEffect,
    ModelCall,
    ModelStepEffect,
    PromotionDecision,
    RelationshipRevision,
    SourceRevision,
    StepEffect,
    StructuredSummaryRevision,
)

ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parents[2] / "alembic-v2.ini"
IMMUTABLE_MODELS = (
    SourceRevision,
    EvidenceFragment,
    CanonNodeRevision,
    RelationshipRevision,
    AuditDecisionRecord,
    PromotionDecision,
    ModelCall,
    ContextManifest,
    ModelStepEffect,
    StepEffect,
    IntegrationEffect,
    StructuredSummaryRevision,
)


def create_sqlite_engine(database_path: Path, *, busy_timeout_ms: int = 5000) -> Engine:
    path = Path(database_path)
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        cursor.close()

    return engine


def bootstrap_schema(engine: Engine) -> None:
    """Compatibility wrapper that migrates an isolated v2 database to head."""
    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


class SchemaValidationError(RuntimeError):
    pass


class ImmutableRecordError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def reject_immutable_changes(
    session: Session, _context: object, _instances: object
) -> None:
    for record in (*session.dirty, *session.deleted):
        if isinstance(record, IMMUTABLE_MODELS):
            raise ImmutableRecordError(f"{record.__tablename__} is immutable")


def _alembic_config() -> Config:
    return Config(ALEMBIC_CONFIG_PATH)


def _expected_head() -> str:
    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    if head is None:
        raise SchemaValidationError("v2 Alembic configuration has no head revision")
    return head


def validate_initialized_schema(
    engine: Engine,
    *,
    require_seed: bool = True,
    seed_path: Path | None = None,
) -> None:
    try:
        schema = inspect(engine)
        present = set(schema.get_table_names())
    except Exception as error:
        raise SchemaValidationError(
            "database is not a readable v2 SQLite database"
        ) from error
    required = set(Base.metadata.tables)
    missing = sorted(required - present)
    if missing:
        raise SchemaValidationError(
            "v2 schema is not initialized; "
            f"missing: {missing[0]}; run initialize or alembic upgrade head"
        )
    for table_name, table in Base.metadata.tables.items():
        present_columns = {column["name"] for column in schema.get_columns(table_name)}
        missing_columns = sorted(set(table.columns.keys()) - present_columns)
        if missing_columns:
            raise SchemaValidationError(
                "v2 schema is incomplete; missing column "
                f"{table_name}.{missing_columns[0]}; run alembic upgrade head"
            )
    with engine.connect() as connection:
        current_heads = MigrationContext.configure(connection).get_current_heads()
        expected_head = _expected_head()
        if current_heads != (expected_head,):
            current = ", ".join(current_heads) if current_heads else "base/unversioned"
            raise SchemaValidationError(
                f"v2 schema revision is {current}, expected {expected_head}; "
                "run initialize or alembic upgrade head"
            )
        if connection.execute(text("PRAGMA foreign_keys")).scalar_one() != 1:
            raise SchemaValidationError("v2 database must enable SQLite foreign keys")
        violations = connection.execute(text("PRAGMA foreign_key_check")).all()
        if violations:
            raise SchemaValidationError("v2 database failed foreign_key_check")
        if (
            require_seed
            and connection.execute(text("SELECT COUNT(*) FROM seed_run")).scalar_one()
            < 1
        ):
            raise SchemaValidationError("v2 world seed has not been imported")
        if seed_path is not None:
            source_hash = hashlib.sha256(Path(seed_path).read_bytes()).hexdigest()
            matched = connection.execute(
                text("SELECT COUNT(*) FROM seed_run WHERE source_hash = :source_hash"),
                {"source_hash": source_hash},
            ).scalar_one()
            if matched < 1:
                raise SchemaValidationError("configured world seed was not imported")
