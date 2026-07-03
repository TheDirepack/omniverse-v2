import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session, select
from app.db.schema import Universe, ProviderConfig, ProviderKey, AgentRouteFallback
from tests.provider_config import PROVIDER_CREDENTIALS


def create_test_db(db_dir: str | Path):
    db_dir = Path(db_dir)
    db_path = db_dir / "omniverse_v2.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    SQLModel.metadata.create_all(engine)

    # Run same migration ALTER TABLEs as init_db() (idempotent on fresh schema)
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(universe)").fetchall()]
        if "is_explored" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN is_explored BOOLEAN NOT NULL DEFAULT 0")
        if "raw_data" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN raw_data TEXT")

        route_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(agentroutefallback)").fetchall()]
        if "model_name" in route_columns and "models" not in route_columns:
            conn.exec_driver_sql("ALTER TABLE agentroutefallback ADD COLUMN models TEXT")
            conn.exec_driver_sql("UPDATE agentroutefallback SET models = model_name")
        if "model_name" in route_columns and "models" in route_columns:
            conn.exec_driver_sql("ALTER TABLE agentroutefallback DROP COLUMN model_name")

        provider_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(providerconfig)").fetchall()]
        if "provider_type" in provider_columns and "base_url" in provider_columns:
            conn.exec_driver_sql(
                "UPDATE providerconfig SET provider_type = 'custom' WHERE provider_type = 'openai' AND base_url IS NOT NULL AND base_url != ''"
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
                base_url=base_url if base_url else None,
                models=model,
            )
            session.add(p)
            session.flush()

            if api_key:
                session.add(ProviderKey(provider_id=p.id, api_key=api_key, priority=0))

        # Seed worlds
        for name in ["Real Life & History (Earth-0)", "Warhammer 40,000", "TestUniverse"]:
            exists = session.exec(select(Universe).where(Universe.name == name)).first()
            if not exists:
                session.add(Universe(name=name, summary=None, is_explored=False))

        # Seed default route
        existing_route = session.exec(select(AgentRouteFallback)).first()
        if not existing_route:
            session.add(AgentRouteFallback(task_type="DEFAULT", priority=0, provider_id=None, models=None))

        session.commit()

    engine.dispose()
