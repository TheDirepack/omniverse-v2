import os
from pathlib import Path

from sqlalchemy import event
from sqlmodel import create_engine

from app.db.extrapolation_schema import extrapolation_metadata

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

EXTRAPOLATION_DB_URL = os.getenv(
    "EXTRAPOLATION_DB_URL", f"sqlite:///{_DATA_DIR / 'extrapolation.db'}"
)
connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(EXTRAPOLATION_DB_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_extrapolation_db():
    extrapolation_metadata.create_all(engine)


def reset_extrapolation_db():
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        extrapolation_metadata.drop_all(conn, checkfirst=True)
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.commit()
    init_extrapolation_db()
