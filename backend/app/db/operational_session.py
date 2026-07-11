import os
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

operational_url = os.getenv(
    "OPERATIONAL_DATABASE_URL", f"sqlite:///{_DATA_DIR / 'operational.db'}"
)
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if operational_url.startswith("sqlite")
    else {}
)
operational_engine = create_engine(operational_url, connect_args=connect_args)

@event.listens_for(operational_engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def init_operational_db():
    print(f"Initializing operational DB with tables: {SQLModel.metadata.tables.keys()}")
    SQLModel.metadata.create_all(operational_engine)



def get_operational_session():
    return Session(operational_engine)
