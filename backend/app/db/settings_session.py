import os
from pathlib import Path

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.schema import AgentRouteFallback, ProviderConfig, Setting
from app.repositories.settings import SettingsRepository

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

settings_url = os.getenv(
    "SETTINGS_DATABASE_URL", f"sqlite:///{_DATA_DIR / 'settings.db'}"
)
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if settings_url.startswith("sqlite")
    else {}
)
settings_engine = create_engine(settings_url, connect_args=connect_args)

@event.listens_for(settings_engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

def init_settings_db():
    SQLModel.metadata.create_all(settings_engine)

    with Session(settings_engine) as session:
        session.execute(text("PRAGMA foreign_keys = ON"))

        # Create default provider
        existing_provider = session.exec(select(ProviderConfig)).first()
        if not existing_provider:
            print("[init_settings_db] No providers found — seeding default provider.")
            session.add(
                ProviderConfig(
                    name="DEFAULT",
                    provider_type="custom",
                    base_url="http://localhost:8001",
                    models="gpt-4o,gpt-4o-mini,claude-3.5",
                )
            )

        existing = session.exec(select(AgentRouteFallback)).first()
        if not existing:
            provider_id = session.exec(
                select(ProviderConfig).order_by(ProviderConfig.id.asc())
            ).first().id
            print(
                "[init_settings_db] No agent routes found — "
                f"seeding DEFAULT fallback route with provider_id={provider_id}."
            )
            session.add(
                AgentRouteFallback(
                    task_type="DEFAULT",
                    priority=0,
                    provider_id=provider_id,
                    models="gpt-4o,gpt-4o-mini,claude-3.5",
                )
            )

        existing_depth = session.get(Setting, "max_composition_depth")
        if not existing_depth:
            session.add(Setting(key="max_composition_depth", value="2"))

        # Bootstrap default settings
        repo = SettingsRepository(session)
        repo.bootstrap_default_settings()

        session.commit()



def reset_settings_db():
    from app.db.session import _drop_all_tables
    _drop_all_tables(settings_engine, SQLModel.metadata)
    init_settings_db()


def get_settings_session():
    return Session(settings_engine)
