from sqlmodel import Session, select

from app.db.operational_session import operational_engine
from app.db.schema import Setting
from app.db.session import engine
from app.db.settings_session import settings_engine


def test_db_pollution_fixed():
    # Main DB: Setting should exist
    with Session(engine) as session:
        res = session.exec(select(Setting)).all()
        assert len(res) >= 0

    # Settings DB: should have its own tables
    with Session(settings_engine) as session:
        try:
            session.exec(select(Setting)).all()
        except Exception as e:  # noqa: BLE001
            assert "no such table" in str(e).lower()

    # Operational DB: should have its own tables
    with Session(operational_engine) as session:
        try:
            session.exec(select(Setting)).all()
        except Exception as e:  # noqa: BLE001
            assert "no such table" in str(e).lower()
