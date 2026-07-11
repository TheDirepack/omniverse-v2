import os
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.db.unconfirmed_schema import unconfirmed_metadata

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

UNCONFIRMED_DB_URL = os.getenv(
    "UNCONFIRMED_DB_URL", f"sqlite:///{_DATA_DIR / 'unconfirmed.db'}"
)
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if UNCONFIRMED_DB_URL.startswith("sqlite")
    else {}
)
unconfirmed_engine = create_engine(UNCONFIRMED_DB_URL, connect_args=connect_args)


@event.listens_for(unconfirmed_engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_unconfirmed_db():
    unconfirmed_metadata.create_all(unconfirmed_engine)


def get_unconfirmed_session():
    return Session(unconfirmed_engine)
