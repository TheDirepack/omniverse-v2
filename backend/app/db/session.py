import os
import json
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event
from app.db.schema import Universe, AgentRouteFallback, Setting
from app.db.unconfirmed_session import init_unconfirmed_db
from app.db.extrapolation_session import init_extrapolation_db

sqlite_url = os.getenv("DATABASE_URL", "sqlite:///omniverse_v2.db")
connect_args = {"check_same_thread": False} if sqlite_url.startswith("sqlite") else {}
engine = create_engine(sqlite_url, connect_args=connect_args)

@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def init_db():
    # Handle CandidateHealth migration: drop if missing candidate_hash PK
    with engine.begin() as conn:
        res = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='candidatehealth'").fetchall()
        if res:
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(candidatehealth)").fetchall()]
            if "candidate_hash" not in columns:
                print("[init_db] CandidateHealth missing candidate_hash. Dropping table for recreation.")
                conn.exec_driver_sql("DROP TABLE candidatehealth")

    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(universe)").fetchall()]
        if "is_explored" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN is_explored BOOLEAN NOT NULL DEFAULT 0")
        if "raw_data" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN raw_data TEXT")
        if "slug" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN slug TEXT")
        if "franchise" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN franchise TEXT")
        if "category" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN category TEXT")
        if "continuity" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN continuity TEXT")
        if "era" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN era TEXT")
        if "parent_id" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN parent_id INTEGER")
        
        # Migrate AgentRouteFallback: model_name -> models
        route_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(agentroutefallback)").fetchall()]
        if "model_name" in route_columns and "models" not in route_columns:
            conn.exec_driver_sql("ALTER TABLE agentroutefallback ADD COLUMN models TEXT")
            conn.exec_driver_sql("UPDATE agentroutefallback SET models = model_name")
        # Drop stale model_name column if both exist
        if "model_name" in route_columns and "models" in route_columns:
            conn.exec_driver_sql("ALTER TABLE agentroutefallback DROP COLUMN model_name")

        # Migrate TierSystem into a persistent, versioned rubric
        tiersystem_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tiersystem)").fetchall()]
        if tiersystem_columns:
            if "version" not in tiersystem_columns:
                conn.exec_driver_sql("ALTER TABLE tiersystem ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            if "is_active" not in tiersystem_columns:
                conn.exec_driver_sql("ALTER TABLE tiersystem ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
                # Only the most recent pre-existing rubric (if any) should be considered active
                conn.exec_driver_sql(
                    "UPDATE tiersystem SET is_active = 0 WHERE id NOT IN (SELECT id FROM tiersystem ORDER BY created_at DESC LIMIT 1)"
                )
            if "parent_id" not in tiersystem_columns:
                conn.exec_driver_sql("ALTER TABLE tiersystem ADD COLUMN parent_id INTEGER")
            if "amendment_reason" not in tiersystem_columns:
                conn.exec_driver_sql("ALTER TABLE tiersystem ADD COLUMN amendment_reason TEXT")

        # Migrate old 'openai' provider_type rows that have a custom base_url → 'custom'
        provider_columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(providerconfig)").fetchall()]
        if "provider_type" in provider_columns and "base_url" in provider_columns:
            conn.exec_driver_sql(
                "UPDATE providerconfig SET provider_type = 'custom' WHERE provider_type = 'openai' AND base_url IS NOT NULL AND base_url != ''"
            )
        
        # NB: 'custom' provider_type stored as-is; router maps to 'openai' at call time
    
    # Seed default route if no routes exist
    with Session(engine) as session:
        existing = session.exec(select(AgentRouteFallback)).first()
        if not existing:
            print("[init_db] No agent routes found — seeding DEFAULT fallback route.")
            session.add(AgentRouteFallback(task_type="DEFAULT", priority=0, provider_id=None, models=None))
            session.commit()
    
    # Initial world seeding from JSON
    try:
        json_path = Path(__file__).parent / "default_worlds.json"
        if json_path.exists():
            with open(json_path, "r") as f:
                default_worlds = json.load(f)
            
            with Session(engine) as session:
                # First pass: Create all universes to get IDs
                slug_to_id = {}
                for w_data in default_worlds:
                    slug = w_data.get("id")
                    exists = session.exec(select(Universe).where(Universe.slug == slug)).first()
                    if not exists:
                        u = Universe(
                            slug=slug,
                            name=w_data.get("name"),
                            franchise=w_data.get("franchise"),
                            category=w_data.get("category"),
                            continuity=w_data.get("continuity"),
                            era=w_data.get("era"),
                            summary=None,
                            is_explored=False
                        )
                        session.add(u)
                        session.flush()
                        slug_to_id[slug] = u.id
                    elif exists:
                        slug_to_id[slug] = exists.id
                
                # Second pass: Set parents
                for w_data in default_worlds:
                    slug = w_data.get("id")
                    parent_slug = w_data.get("parent")
                    if parent_slug:
                        u = session.exec(select(Universe).where(Universe.slug == slug)).first()
                        if u and parent_slug in slug_to_id:
                            u.parent_id = slug_to_id[parent_slug]
                
                session.commit()
    except Exception as e:
        print(f"Error seeding default worlds: {e}")

    # Seed default inference composition depth (configurable via Settings UI;
    # kept small since composition depth grows combinatorially in dense graphs)
    with Session(engine) as session:
        existing_depth = session.get(Setting, "max_composition_depth")
        if not existing_depth:
            session.add(Setting(key="max_composition_depth", value="2"))
            session.commit()

    # Initialize the separate unconfirmed staging database
    try:
        init_unconfirmed_db()
    except Exception as e:
        print(f"Error initializing unconfirmed database: {e}")

    # Initialize the extrapolation database
    try:
        init_extrapolation_db()
    except Exception as e:
        print(f"Error initializing extrapolation database: {e}")

    # Initialize the separate settings database (providers, routing,
    # general settings). This was previously never called anywhere in the
    # app -- on a fresh deployment, settings.db would have no tables at all
    # until someone manually ran a migration script, causing "no such
    # table: setting" the moment anything touched SettingsService.
    try:
        from app.db.settings_session import init_settings_db
        init_settings_db()
    except Exception as e:
        print(f"Error initializing settings database: {e}")
