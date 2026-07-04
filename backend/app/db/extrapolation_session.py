import os
from sqlmodel import create_engine
from sqlalchemy import event
from app.db.extrapolation_schema import extrapolation_metadata

EXTRAPOLATION_DB_URL = os.getenv("EXTRAPOLATION_DB_URL", "sqlite:///extrapolation.db")
connect_args = {"check_same_thread": False}
engine = create_engine(EXTRAPOLATION_DB_URL, connect_args=connect_args)

@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def init_extrapolation_db():
    extrapolation_metadata.create_all(engine)
