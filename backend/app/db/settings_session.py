import os

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
os.makedirs(_DATA_DIR, exist_ok=True)

settings_url = os.getenv("SETTINGS_DATABASE_URL", f"sqlite:///{os.path.join(_DATA_DIR, 'settings.db')}")
connect_args = {"check_same_thread": False, "timeout": 30} if settings_url.startswith("sqlite") else {}
settings_engine = create_engine(settings_url, connect_args=connect_args)

@event.listens_for(settings_engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

from app.db.schema import Setting, ProviderConfig, ProviderKey, AgentRouteFallback
from sqlmodel import select

def init_settings_db():
    SQLModel.metadata.create_all(settings_engine)

    with Session(settings_engine) as session:
        session.execute(text("PRAGMA foreign_keys = ON"))

        existing = session.exec(select(AgentRouteFallback)).first()
        if not existing:
            print("[init_settings_db] No agent routes found — seeding DEFAULT fallback route.")
            session.add(
                AgentRouteFallback(
                    task_type="DEFAULT",
                    priority=0,
                    provider_id=None,
                    models=None,
                )
            )

        existing_depth = session.get(Setting, "max_composition_depth")
        if not existing_depth:
            session.add(Setting(key="max_composition_depth", value="2"))

        session.commit()



def get_settings_session():
    return Session(settings_engine)
