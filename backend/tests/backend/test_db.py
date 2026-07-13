from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.schema import AgentRouteFallback, ProviderConfig, ProviderKey, Universe, Artifact, ArtifactRelation

try:
    from tests.provider_config import PROVIDER_CREDENTIALS
except ImportError:
    pytest.importorskip("tests.provider_config")

from scripts.migrate_universe_metadata_to_artifacts import migrate

def create_test_db(db_dir: str | Path, db_filename: str = "omniverse_v2.db"):
    db_dir = Path(db_dir)
    db_path = db_dir / db_filename
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    SQLModel.metadata.create_all(engine)

    # Run same migration ALTER TABLEs as init_db() (idempotent on fresh schema)
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        columns = [
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(universe)").fetchall()
        ]
        if "is_explored" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE universe ADD COLUMN is_explored BOOLEAN NOT NULL DEFAULT 0"
            )
        if "raw_data" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN raw_data TEXT")

        route_columns = [
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA table_info(agentroutefallback)"
            ).fetchall()
        ]
        if "model_name" in route_columns and "models" not in route_columns:
            conn.exec_driver_sql(
                "ALTER TABLE agentroutefallback ADD COLUMN models TEXT"
            )
            conn.exec_driver_sql("UPDATE agentroutefallback SET models = model_name")
        if "model_name" in route_columns and "models" in route_columns:
            conn.exec_driver_sql(
                "ALTER TABLE agentroutefallback DROP COLUMN model_name"
            )

        provider_columns = [
            row[1]
            for row in conn.exec_driver_sql(
                "PRAGMA table_info(providerconfig)"
            ).fetchall()
        ]
        if "provider_type" in provider_columns and "base_url" in provider_columns:
            conn.exec_driver_sql(
                "UPDATE providerconfig SET provider_type = 'custom' "
                "WHERE provider_type = 'openai' AND base_url IS NOT NULL "
                "AND base_url != ''"
            )

    # Seed providers
    with Session(engine) as session:
        for ptype, creds in PROVIDER_CREDENTIALS.items():
            api_key = creds.get("api_key")
            base_url = creds.get("base_url")
            if not api_key and not base_url:
                continue

            model = creds.get("model") or None
            p = ProviderConfig(
                name=f"test-{ptype}",
                provider_type=ptype,
                base_url=base_url or None,
                models=model,
            )
            session.add(p)
            session.flush()

            if api_key:
                session.add(ProviderKey(provider_id=p.id, api_key=api_key, priority=0))

        # Seed worlds
        for name in [
            "Real Life & History (Earth-0)",
            "Warhammer 40,000",
            "TestUniverse",
        ]:
            exists = session.exec(select(Universe).where(Universe.name == name)).first()
            if not exists:
                session.add(Universe(name=name, summary=None, is_explored=False))

        # Seed default route
        existing_route = session.exec(select(AgentRouteFallback)).first()
        if not existing_route:
            session.add(
                AgentRouteFallback(
                    task_type="DEFAULT", priority=0, provider_id=None, models=None
                )
            )

        session.commit()

    engine.dispose()

def test_universe_metadata_columns_removed():
    # Assert that Universe model no longer has franchise, category, continuity, era
    assert not hasattr(Universe, "franchise")
    assert not hasattr(Universe, "category")
    assert not hasattr(Universe, "continuity")
    assert not hasattr(Universe, "era")

def test_migration_moves_metadata_to_artifacts(tmp_path):
    db_dir = tmp_path / "test_db"
    db_dir.mkdir()
    db_filename = "test_migration.db"
    create_test_db(db_dir, db_filename)
    
    db_path = db_dir / db_filename
    db_url = f"sqlite:///{db_path}"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Seed a universe with metadata
    with Session(test_engine) as session:
        universe = Universe(
            name="Migration Test Universe",
            franchise="Test Franchise",
            category="Test Category",
            continuity="Test Continuity",
            era="Test Era"
        )
        session.add(universe)
        session.commit()
        universe_id = universe.id

    # Run migration
    migrate(engine_override=test_engine)

    # Verify migration
    with Session(test_engine) as session:
        # Check for Artifacts
        artifacts = session.exec(
            select(Artifact).where(Artifact.universe_id == universe_id)
        ).all()
        
        artifact_types = {a.type: a.name for a in artifacts}
        assert artifact_types["franchise"] == "Test Franchise"
        assert artifact_types["category"] == "Test Category"
        assert artifact_types["continuity"] == "Test Continuity"
        assert artifact_types["era"] == "Test Era"
        assert artifact_types["world"] == "Migration Test Universe"

        # Check for Relations
        relations = session.exec(
            select(ArtifactRelation).where(ArtifactRelation.universe_id == universe_id)
        ).all()
        
        # We expect 4 relations: world -> franchise, world -> category, world -> continuity, world -> era
        assert len(relations) == 4
        
        relation_types = [r.relation_type for r in relations]
        assert all(rt == "PART_OF" for rt in relation_types)
