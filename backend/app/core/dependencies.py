from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.db.session import engine
from app.db.settings_session import settings_engine
from app.db.notebook_session import notebook_engine
from app.services.settings_service import SettingsService
from app.services.universe_service import UniverseService


def get_settings_session() -> Session:
    with Session(settings_engine) as session:
        yield session

def get_notebook_session() -> Session:
    with Session(notebook_engine) as session:
        yield session

def get_settings_service(
    session: Annotated[Session, Depends(get_settings_session)],
) -> SettingsService:
    return SettingsService(session=session)

def get_main_session() -> Session:
    with Session(engine) as session:
        yield session

def get_universe_session(session: Annotated[Session, Depends(get_main_session)]) -> Session:
    return session

def get_universe_service(
    session: Annotated[Session, Depends(get_universe_session)],
) -> UniverseService:
    return UniverseService(session=session)
