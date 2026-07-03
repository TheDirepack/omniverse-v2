import os
import json
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import event
from app.db.schema import Universe

sqlite_url = os.getenv("DATABASE_URL", "sqlite:///omniverse_v2.db")
connect_args = {"check_same_thread": False} if sqlite_url.startswith("sqlite") else {}
engine = create_engine(sqlite_url, connect_args=connect_args)

@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def init_db():
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(universe)").fetchall()]
        if "is_explored" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN is_explored BOOLEAN NOT NULL DEFAULT 0")
        if "raw_data" not in columns:
            conn.exec_driver_sql("ALTER TABLE universe ADD COLUMN raw_data TEXT")
    
    # Initial world seeding from JSON
    try:
        json_path = Path(__file__).parent / "default_worlds.json"
        if json_path.exists():
            with open(json_path, "r") as f:
                default_worlds = json.load(f)
            
            with Session(engine) as session:
                for name in default_worlds:
                    # Only add if not already present
                    exists = session.exec(select(Universe).where(Universe.name == name)).first()
                    if not exists:
                        session.add(Universe(name=name, summary=None, is_explored=False))
                session.commit()
    except Exception as e:
        print(f"Error seeding default worlds: {e}")
