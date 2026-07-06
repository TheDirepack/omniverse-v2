import os
from sqlmodel import SQLModel, create_engine, Session

settings_url = os.getenv("SETTINGS_DATABASE_URL", "sqlite:///settings.db")
connect_args = {"check_same_thread": False} if settings_url.startswith("sqlite") else {}
settings_engine = create_engine(settings_url, connect_args=connect_args)

def init_settings_db():
    # Only create tables related to settings
    # We use a separate metadata or just create all and rely on the fact 
    # that only these are used here. 
    # Actually, SQLModel.metadata.create_all(settings_engine) will create ALL tables 
    # defined in the app. We probably want to be specific or just accept it 
    # as settings.db will only ever be queried for these tables.
    SQLModel.metadata.create_all(settings_engine)

def get_settings_session():
    return Session(settings_engine)
