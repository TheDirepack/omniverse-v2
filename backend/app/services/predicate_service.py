from typing import Optional
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import Predicate, PredicateAlias
from app.services.ontology_service import OntologyService

class PredicateService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self.ontology = OntologyService(session)

    def normalize(self, raw_predicate: str) -> str:
        """
        Maps a raw predicate string to its canonical version using 
        aliases and the semantic ontology.
        """
        normalized_raw = raw_predicate.strip().upper()
        
        with Session(engine) if not self.session else self.session as session:
            # 1. Check Aliases
            alias = session.exec(select(PredicateAlias).where(PredicateAlias.alias == normalized_raw)).first()
            if alias:
                # Find the root canonical name via ontology
                return self.ontology.get_canonical_group(alias.canonical_name)
            
            # 2. Check if it's already a known canonical predicate
            pred = session.exec(select(Predicate).where(Predicate.canonical_name == normalized_raw)).first()
            if pred:
                return self.ontology.get_canonical_group(normalized_raw)
                
        return normalized_raw

                
        return normalized_raw

    def upsert_alias(self, alias: str, canonical_name: str):
        with Session(engine) if not self.session else self.session as session:
            # Ensure canonical predicate exists
            pred = session.exec(select(Predicate).where(Predicate.canonical_name == canonical_name)).first()
            if not pred:
                session.add(Predicate(canonical_name=canonical_name))
                session.flush()
            
            # Upsert alias
            existing_alias = session.exec(select(PredicateAlias).where(PredicateAlias.alias == alias)).first()
            if existing_alias:
                existing_alias.canonical_name = canonical_name
                session.add(existing_alias)
            else:
                session.add(PredicateAlias(alias=alias, canonical_name=canonical_name))
            
            session.commit()
