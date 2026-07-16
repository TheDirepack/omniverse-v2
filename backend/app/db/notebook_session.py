import os
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.db.notebook_schema import notebook_metadata

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

NOTEBOOK_DB_URL = os.getenv(
    "NOTEBOOK_DB_URL", f"sqlite:///{_DATA_DIR / 'notebook.db'}"
)
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if NOTEBOOK_DB_URL.startswith("sqlite")
    else {}
)
notebook_engine = create_engine(NOTEBOOK_DB_URL, connect_args=connect_args)


@event.listens_for(notebook_engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_notebook_db():
    notebook_metadata.create_all(notebook_engine)


def reset_notebook_db():
    with notebook_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = OFF")
        notebook_metadata.drop_all(conn, checkfirst=True)
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        conn.commit()
    init_notebook_db()


def get_notebook_session():
    return Session(notebook_engine)
