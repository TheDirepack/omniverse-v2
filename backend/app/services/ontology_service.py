from typing import Optional, List, Dict
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Predicate

class OntologyService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session

    def get_canonical_group(self, predicate_name: str) -> str:
        """
        Traverses the predicate hierarchy upwards to find the root canonical 
        predicate for a given name. This ensures that 'resides_in' and 
        'is_located_in' both map to 'LOCATED_IN' if that's the root.
        """
        with Session(engine) if not self.session else self.session as session:
            # Find the predicate entry
            pred = session.exec(select(Predicate).where(Predicate.canonical_name == predicate_name)).first()
            if not pred:
                return predicate_name
            
            # Traverse up the parent chain
            current = pred
            while current.parent_predicate_id:
                parent = session.get(Predicate, current.parent_predicate_id)
                if not parent:
                    break
                current = parent
            
            return current.canonical_name

    def define_relationship(self, child_name: str, parent_name: str):
        """Defines that child_name is a specific type of parent_name."""
        with Session(engine) if not self.session else self.session as session:
            child = session.exec(select(Predicate).where(Predicate.canonical_name == child_name)).first()
            parent = session.exec(select(Predicate).where(Predicate.canonical_name == parent_name)).first()
            
            if not child:
                child = Predicate(canonical_name=child_name)
                session.add(child)
                session.flush()
            
            if not parent:
                parent = Predicate(canonical_name=parent_name)
                session.add(parent)
                session.flush()
            
            child.parent_predicate_id = parent.id
            session.add(child)
            session.commit()
