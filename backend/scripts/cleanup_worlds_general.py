import re

from sqlmodel import Session, select

from app.db.schema import Universe
from app.db.session import engine
from app.db.unconfirmed_schema import UnconfirmedUniverse
from app.db.unconfirmed_session import unconfirmed_engine

# Pattern to match trailing parentheses: optional space, then
# (anything) at the end of the string
PATTERN = r"\s*\([^)]*\)$"


def clean_name(name):
    if not name:
        return name
    return re.sub(PATTERN, "", name, flags=re.IGNORECASE).strip()


def main():
    # Main DB
    with Session(engine) as session:
        universes = session.exec(select(Universe)).all()
        updated_count = 0
        for u in universes:
            cleaned = clean_name(u.name)
            if cleaned != u.name:
                print(f"Main DB: {u.name} -> {cleaned}")
                u.name = cleaned
                updated_count += 1
        session.commit()
        print(f"Updated {updated_count} universes in main DB.")

    # Unconfirmed DB
    with Session(unconfirmed_engine) as session:
        universes = session.exec(select(UnconfirmedUniverse)).all()
        updated_count = 0
        for u in universes:
            cleaned = clean_name(u.name)
            if cleaned != u.name:
                print(f"Unconfirmed DB: {u.name} -> {cleaned}")
                u.name = cleaned
                updated_count += 1
        session.commit()
        print(f"Updated {updated_count} universes in unconfirmed DB.")


if __name__ == "__main__":
    main()
