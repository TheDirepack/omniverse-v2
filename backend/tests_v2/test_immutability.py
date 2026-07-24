from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.v2 import db
from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.models import Source, SourceRevision

IMMUTABLE_TABLES = {
    "source_revision",
    "evidence_fragment",
    "canon_node_revision",
    "relationship_revision",
    "audit_decision",
    "promotion_decision",
    "model_call",
    "context_manifest",
    "model_step_effect",
    "step_effect",
    "integration_effect",
    "structured_summary_revision",
}


@pytest.fixture
def immutable_engine(isolated_paths: dict[str, Path]):
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as session, session.begin():
        session.add(Source(id="source", canonical_url="https://example.invalid/one"))
        session.add(
            SourceRevision(id="revision", source_id="source", content_hash="a" * 64)
        )
    return engine


@pytest.mark.integration
def test_application_rejects_immutable_revision_update(immutable_engine) -> None:
    with Session(immutable_engine) as session:
        revision = session.get(SourceRevision, "revision")
        assert revision is not None
        revision.content_hash = "b" * 64
        with pytest.raises(db.ImmutableRecordError, match="source_revision"):
            session.commit()


@pytest.mark.integration
def test_all_immutable_records_are_guarded_in_application_and_database(
    immutable_engine,
) -> None:
    assert {model.__tablename__ for model in db.IMMUTABLE_MODELS} == IMMUTABLE_TABLES
    with immutable_engine.connect() as connection:
        trigger_names = set(
            connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
            ).scalars()
        )
    assert trigger_names == {
        f"immutable_{table}_{operation}"
        for table in IMMUTABLE_TABLES
        for operation in ("update", "delete")
    }


@pytest.mark.integration
def test_new_revision_can_be_appended(immutable_engine) -> None:
    with Session(immutable_engine) as session, session.begin():
        session.add(
            SourceRevision(
                id="superseding-revision",
                source_id="source",
                content_hash="c" * 64,
            )
        )
    with Session(immutable_engine) as session:
        assert session.get(SourceRevision, "revision") is not None
        assert session.get(SourceRevision, "superseding-revision") is not None


@pytest.mark.integration
@pytest.mark.parametrize("statement", ["UPDATE", "DELETE"])
def test_database_rejects_immutable_revision_changes(
    immutable_engine, statement: str
) -> None:
    sql = (
        "UPDATE source_revision SET content_hash = :hash WHERE id = 'revision'"
        if statement == "UPDATE"
        else "DELETE FROM source_revision WHERE id = 'revision'"
    )
    with (
        pytest.raises(DatabaseError, match="immutable"),
        immutable_engine.begin() as connection,
    ):
        connection.execute(text(sql), {"hash": "b" * 64})


@pytest.mark.integration
def test_immutable_failure_rolls_back_the_whole_transaction(immutable_engine) -> None:
    with (
        pytest.raises(DatabaseError, match="immutable"),
        immutable_engine.begin() as connection,
    ):
        connection.execute(
            text(
                "INSERT INTO source (id, canonical_url, source_class) "
                "VALUES ('rolled-back', 'https://example.invalid/two', 'SECONDARY')"
            )
        )
        connection.execute(
            text(
                "UPDATE source_revision SET content_hash = :hash WHERE id = 'revision'"
            ),
            {"hash": "b" * 64},
        )

    with immutable_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM source WHERE id = 'rolled-back'")
            ).scalar_one()
            == 0
        )
