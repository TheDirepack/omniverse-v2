import os
from pathlib import Path

from sqlalchemy import event
from sqlmodel import SQLModel, create_engine

# Import schema to register models with SQLModel.metadata
import app.db.schema  # noqa: F401
from app.db.extrapolation_session import init_extrapolation_db
from app.db.notebook_session import init_notebook_db

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

sqlite_url = os.getenv(
    "DATABASE_URL", f"sqlite:///{_DATA_DIR / 'omniverse_v2.db'}"
)
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if sqlite_url.startswith("sqlite")
    else {}
)
engine = create_engine(sqlite_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db(engine_override=None):
    target_engine = engine_override or engine
    print(f"Creating tables: {SQLModel.metadata.tables.keys()}")
    SQLModel.metadata.create_all(target_engine)

    # Initialize the operational database
    try:
        from app.db.operational_session import init_operational_db
        init_operational_db()
    except Exception as e:
        print(f"Error initializing operational database: {e}")

    # Initialize the separate notebook staging database
    try:
        init_notebook_db()
    except Exception as e:
        print(f"Error initializing notebook database: {e}")

    # Initialize the extrapolation database
    try:
        init_extrapolation_db()
    except Exception as e:
        print(f"Error initializing extrapolation database: {e}")

    # Initialize the separate settings database
    try:
        from app.db.settings_session import init_settings_db
        init_settings_db()
    except Exception as e:
        print(f"Error initializing settings database: {e}")


def _drop_all_tables(engine, metadata):
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        metadata.drop_all(conn, checkfirst=True)
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.commit()


def reset_main_db():
    _drop_all_tables(engine, SQLModel.metadata)
    init_db()
