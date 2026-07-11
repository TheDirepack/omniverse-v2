import os
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from sqlmodel import Session, SQLModel, create_engine, select

from app.db.schema import (
    AgentRouteFallback,
    CandidateHealth,
    ModelConfig,
    ProviderConfig,
    ProviderKey,
    Setting,
)


def migrate():
    main_db_url = os.getenv("DATABASE_URL", "sqlite:///omniverse_v2.db")
    settings_db_url = os.getenv("SETTINGS_DATABASE_URL", "sqlite:///settings.db")

    main_engine = create_engine(main_db_url)
    settings_engine = create_engine(settings_db_url)

    # Ensure settings tables exist
    SQLModel.metadata.create_all(settings_engine)

    with Session(main_engine) as main_session, Session(settings_engine) as set_session:
        print("Migrating Settings...")
        settings = main_session.exec(select(Setting)).all()
        for s in settings:
            set_session.add(Setting(key=s.key, value=s.value))

        print("Migrating Providers...")
        providers = main_session.exec(select(ProviderConfig)).all()
        for p in providers:
            set_session.add(
                ProviderConfig(
                    id=p.id,
                    name=p.name,
                    provider_type=p.provider_type,
                    base_url=p.base_url,
                    models=p.models,
                )
            )

        print("Migrating Provider Keys...")
        keys = main_session.exec(select(ProviderKey)).all()
        for k in keys:
            set_session.add(
                ProviderKey(
                    id=k.id,
                    provider_id=k.provider_id,
                    api_key=k.api_key,
                    priority=k.priority,
                )
            )

        print("Migrating Agent Routes...")
        routes = main_session.exec(select(AgentRouteFallback)).all()
        for r in routes:
            set_session.add(
                AgentRouteFallback(
                    id=r.id,
                    task_type=r.task_type,
                    priority=r.priority,
                    provider_id=r.provider_id,
                    models=r.models,
                )
            )

        print("Migrating Model Configs...")
        m_configs = main_session.exec(select(ModelConfig)).all()
        for mc in m_configs:
            set_session.add(
                ModelConfig(
                    id=mc.id, model_name=mc.model_name, provider_id=mc.provider_id
                )
            )

        print("Migrating Candidate Health...")
        health = main_session.exec(select(CandidateHealth)).all()
        for h in health:
            set_session.add(
                CandidateHealth(
                    candidate_hash=h.candidate_hash,
                    provider_id=h.provider_id,
                    key_id=h.key_id,
                    model=h.model,
                    failure_count=h.failure_count,
                    disabled_until=h.disabled_until,
                )
            )

        set_session.commit()
        print("Migration complete.")


if __name__ == "__main__":
    migrate()
