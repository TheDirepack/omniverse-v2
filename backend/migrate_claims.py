import os
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Claim, Predicate

def migrate_predicates():
    with Session(engine) as session:
        # 1. Ensure all currently used predicates are in the Predicate table
        claims = session.exec(select(Claim)).all()
        for claim in claims:
            if claim.predicate:
                pred = session.exec(select(Predicate).where(Predicate.canonical_name == claim.predicate)).first()
                if not pred:
                    print(f"Creating missing predicate: {claim.predicate}")
                    session.add(Predicate(canonical_name=claim.predicate))
        session.commit()
        
        # 2. Map predicate strings to IDs
        predicates = session.exec(select(Predicate)).all()
        pred_map = {p.canonical_name: p.id for p in predicates}
        
        updated_count = 0
        for claim in claims:
            if claim.predicate in pred_map:
                claim.predicate_id = pred_map[claim.predicate]
                session.add(claim)
                updated_count += 1
        
        session.commit()
        print(f"Successfully migrated {updated_count} claims to use predicate_id.")

if __name__ == "__main__":
    migrate_predicates()
