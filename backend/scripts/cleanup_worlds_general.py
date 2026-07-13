import re

from sqlmodel import Session, select

from app.db.schema import Universe
from app.db.session import engine
from app.db.notebook_schema import NotebookUniverse
from app.db.notebook_session import notebook_engine

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

    # Notebook DB
    with Session(notebook_engine) as session:
        universes = session.exec(select(NotebookUniverse)).all()
        updated_count = 0
        for u in universes:
            cleaned = clean_name(u.name)
            if cleaned != u.name:
                print(f"Notebook DB: {u.name} -> {cleaned}")
                u.name = cleaned
                updated_count += 1
        session.commit()
        print(f"Updated {updated_count} universes in notebook DB.")


if __name__ == "__main__":
    main()
