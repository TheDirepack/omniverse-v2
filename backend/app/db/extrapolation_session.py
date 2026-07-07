import os

from sqlalchemy import event
from sqlmodel import create_engine

from app.db.extrapolation_schema import extrapolation_metadata

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
os.makedirs(_DATA_DIR, exist_ok=True)

EXTRAPOLATION_DB_URL = os.getenv("EXTRAPOLATION_DB_URL", f"sqlite:///{os.path.join(_DATA_DIR, 'extrapolation.db')}")
connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(EXTRAPOLATION_DB_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_extrapolation_db():
    extrapolation_metadata.create_all(engine)
