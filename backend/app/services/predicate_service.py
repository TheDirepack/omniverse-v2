from sqlmodel import Session

from app.db.session import engine


class PredicateService:
    """
    Handles normalization of raw predicates into canonical forms.
    Example: 'uses' -> 'POWERED_BY', 'is a' -> 'INSTANCE_OF'.
    """

    # Common aliases for predicate normalization
    ALIASES = {
        "uses": "POWERED_BY",
        "utilizes": "POWERED_BY",
        "is a": "INSTANCE_OF",
        "belongs to": "PART_OF",
        "located in": "SITUATED_AT",
        "created by": "ORIGINATED_FROM",
    }

    def __init__(self, session: Session | None = None):
        self.session = session or Session(engine)

    def normalize(self, predicate: str) -> str:
        if not predicate:
            return "RELATED_TO"

        lower_pred = predicate.lower().strip()

        # 1. Check hardcoded aliases
        if lower_pred in self.ALIASES:
            return self.ALIASES[lower_pred]

        # 2. Fallback: return uppercased raw predicate
        return lower_pred.upper().replace(" ", "_")
