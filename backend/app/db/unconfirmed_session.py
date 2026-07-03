import os
from sqlmodel import create_engine
from sqlalchemy import event
from app.db.unconfirmed_schema import unconfirmed_metadata

UNCONFIRMED_DB_URL = os.getenv("UNCONFIRMED_DB_URL", "sqlite:///unconfirmed.db")
connect_args = {"check_same_thread": False}
engine = create_engine(UNCONFIRMED_DB_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_unconfirmed_db():
    unconfirmed_metadata.create_all(engine)
