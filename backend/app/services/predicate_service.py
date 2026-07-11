from sqlmodel import Session, select

from app.db.schema import Predicate
from app.db.session import engine


class PredicateService:
    def __init__(self, session: Session | None = None):
        self._session = session

    @property
    def session(self) -> Session:
        if self._session is None:
            # In a real app, we'd use a session provider, but for a service
            # called from tools, we can open a temporary session if none provided.
            self._session = Session(engine)
        return self._session

    def normalize(self, predicate: str) -> str:
        if not predicate:
            return "related_to"

        norm = predicate.strip().upper().replace(" ", "_")

        # Try to find a canonical match in the database
        existing = self.session.exec(
            select(Predicate).where(Predicate.canonical_name == norm)
        ).first()

        if existing:
            return existing.canonical_name

        return norm
