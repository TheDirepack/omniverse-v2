from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.v2.db import bootstrap_schema, create_sqlite_engine
from app.v2.models import (
    Base,
    CanonNode,
    CanonNodeRevision,
    EvidenceFragment,
    RelationshipAssertion,
    RelationshipEvidence,
    RelationshipRevision,
    Source,
    SourceRevision,
    World,
)
from app.v2.repositories import add_relationship

EXPECTED_TABLES = {
    "world",
    "continuity",
    "timeline_branch",
    "subject",
    "subject_relation",
    "policy_definition",
    "source",
    "source_revision",
    "evidence_fragment",
    "citation",
    "research_workspace",
    "research_gap",
    "material_proposal",
    "audit_decision",
    "promotion_decision",
    "material_proposal_field",
    "proposal_field_evidence",
    "claim_conflict",
    "run",
    "run_step",
    "step_attempt",
    "checkpoint",
    "outbox_event",
    "tool_event",
    "context_manifest",
    "provider",
    "provider_model",
    "credential_ref",
    "canon_node",
    "canon_node_revision",
    "relationship_assertion",
    "relationship_revision",
    "node_evidence",
    "relationship_evidence",
    "seed_run",
}


@pytest.fixture
def session(isolated_paths: dict[str, object]) -> Session:
    engine = create_sqlite_engine(isolated_paths["database"])
    bootstrap_schema(engine)
    with Session(engine) as value:
        yield value


@pytest.mark.integration
def test_schema_uses_one_metadata_and_has_foundation_without_tiering_or_theory(
    isolated_paths: dict[str, object],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"])
    assert CanonNode.metadata is Base.metadata
    assert RelationshipAssertion.metadata is Base.metadata
    bootstrap_schema(engine)
    tables = set(inspect(engine).get_table_names())
    assert tables >= EXPECTED_TABLES
    assert {"power_profile", "profile_condition"}.isdisjoint(tables)
    assert not any("tier" in name or "theory" in name for name in tables)


@pytest.mark.integration
def test_sqlite_factory_enables_required_pragmas(
    isolated_paths: dict[str, object],
) -> None:
    engine = create_sqlite_engine(isolated_paths["database"], busy_timeout_ms=4321)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert (
            connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower()
            == "wal"
        )
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 4321


@pytest.mark.integration
def test_migration_from_baseline_to_head_adds_freshness_scope_indexes(
    isolated_paths: dict[str, object],
) -> None:
    database = isolated_paths["database"]
    config = Config(str(Path(__file__).parents[1] / "alembic-v2.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "v2_0001_baseline")
    command.upgrade(config, "head")
    engine = create_sqlite_engine(database)
    schema = inspect(engine)
    assert {column["name"] for column in schema.get_columns("coverage_record")} >= {
        "era_or_timepoint",
        "branch_id",
        "conditions_key",
    }
    indexes = {index["name"] for index in schema.get_indexes("coverage_record")}
    assert "ix_coverage_freshness_scope" in indexes
    assert "ix_evidence_freshness_scope" in {
        index["name"] for index in schema.get_indexes("evidence_fragment")
    }


def seed_graph(session: Session) -> tuple[CanonNode, CanonNode, EvidenceFragment]:
    world = World(id="bt", name="BattleTech", franchise="BattleTech", category="SF")
    session.add(world)
    session.flush()
    mechanism = CanonNode(id="fusion", world_id="bt", kind="MECHANISM")
    model = CanonNode(id="atlas", world_id="bt", kind="MODEL")
    session.add_all([mechanism, model])
    session.flush()
    source = Source(id="s1", canonical_url="https://example.invalid/source")
    session.add(source)
    session.flush()
    revision = SourceRevision(id="sr1", source_id="s1", content_hash="a" * 64)
    session.add(revision)
    session.flush()
    evidence = EvidenceFragment(
        id="e1",
        source_revision_id="sr1",
        locator="p1",
        exact_excerpt="text",
        content_hash="b" * 64,
    )
    session.add(evidence)
    session.flush()
    return mechanism, model, evidence


@pytest.mark.integration
def test_relationship_revisions_require_real_evidence(session: Session) -> None:
    mechanism, model, _ = seed_graph(session)
    relation = RelationshipAssertion(
        id="r1", source_node_id=model.id, target_node_id=mechanism.id
    )
    revision = RelationshipRevision(
        id="rr1",
        assertion_id="r1",
        revision_number=1,
        relation_type="IMPLEMENTS",
        scope_json={"world_id": "bt", "continuity": "classic"},
    )
    session.add(relation)
    session.flush()
    session.add(revision)
    session.flush()
    session.add(
        RelationshipEvidence(
            relationship_revision_id="rr1", evidence_fragment_id="missing"
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.integration
def test_generic_mechanism_can_be_referenced_by_multiple_models(
    session: Session,
) -> None:
    mechanism, model, evidence = seed_graph(session)
    second = CanonNode(id="marauder", world_id="bt", kind="MODEL")
    session.add(second)
    session.flush()
    add_relationship(
        session,
        "r1",
        model.id,
        mechanism.id,
        "IMPLEMENTS",
        {"world_id": "bt"},
        evidence.id,
    )
    add_relationship(
        session,
        "r2",
        second.id,
        mechanism.id,
        "IMPLEMENTS",
        {"world_id": "bt"},
        evidence.id,
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(RelationshipAssertion)
            .where(RelationshipAssertion.target_node_id == mechanism.id)
        )
        == 2
    )


@pytest.mark.integration
def test_instance_override_revision_does_not_mutate_model_revision(
    session: Session,
) -> None:
    _, model, _ = seed_graph(session)
    instance = CanonNode(id="atlas-001", world_id="bt", kind="INSTANCE")
    model_revision = CanonNodeRevision(
        id="nr-model",
        node_id=model.id,
        revision_number=1,
        fields_json={"engine": "standard"},
    )
    instance_revision = CanonNodeRevision(
        id="nr-instance",
        node_id=instance.id,
        revision_number=1,
        fields_json={"engine": "damaged"},
    )
    session.add(instance)
    session.flush()
    session.add_all([model_revision, instance_revision])
    session.flush()
    assert model_revision.fields_json == {"engine": "standard"}
    assert instance_revision.fields_json == {"engine": "damaged"}


@pytest.mark.integration
def test_taxonomy_cycles_fail_but_causal_loops_are_allowed(session: Session) -> None:
    _, first, evidence = seed_graph(session)
    second = CanonNode(id="second", world_id="bt", kind="MODEL")
    session.add(second)
    session.flush()
    add_relationship(
        session, "isa1", first.id, second.id, "IS_A", {"world_id": "bt"}, evidence.id
    )
    with pytest.raises(ValueError, match="cycle"):
        add_relationship(
            session,
            "isa2",
            second.id,
            first.id,
            "IS_A",
            {"world_id": "bt"},
            evidence.id,
        )
    session.rollback()

    # Recreate the rolled-back fixture graph for the independent causal case.
    _, first, evidence = seed_graph(session)
    second = CanonNode(id="second", world_id="bt", kind="MODEL")
    session.add(second)
    session.flush()
    add_relationship(
        session,
        "cause1",
        first.id,
        second.id,
        "CAUSES",
        {"world_id": "bt"},
        evidence.id,
    )
    add_relationship(
        session,
        "cause2",
        second.id,
        first.id,
        "CAUSES",
        {"world_id": "bt"},
        evidence.id,
    )
