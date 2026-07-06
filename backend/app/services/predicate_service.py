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
        
        session = self.session or Session(engine)
        try:
            # 1. Check Aliases -- PredicateAlias links to a Predicate via
            # predicate_id (there is no canonical_name column on
            # PredicateAlias itself), so the actual canonical name has to be
            # read off the linked Predicate row.
            alias = session.exec(select(PredicateAlias).where(PredicateAlias.alias == normalized_raw)).first()
            if alias and alias.predicate_id:
                predicate = session.get(Predicate, alias.predicate_id)
                if predicate:
                    return self.ontology.get_canonical_group(predicate.canonical_name)
            
            # 2. Check if it's already a known canonical predicate
            pred = session.exec(select(Predicate).where(Predicate.canonical_name == normalized_raw)).first()
            if pred:
                return self.ontology.get_canonical_group(normalized_raw)
        finally:
            if not self.session:
                session.close()

        return normalized_raw

        return normalized_raw

    def upsert_alias(self, alias: str, canonical_name: str):
        normalized_alias = alias.strip().upper()
        session = self.session or Session(engine)
        try:
            # Ensure canonical predicate exists
            pred = session.exec(select(Predicate).where(Predicate.canonical_name == canonical_name)).first()
            if not pred:
                pred = Predicate(canonical_name=canonical_name)
                session.add(pred)
                session.flush()
            
            # Upsert alias -- must store predicate_id (the real FK on
            # PredicateAlias), not canonical_name (not a field on this model;
            # passing it silently dropped the value and left predicate_id
            # unset, making every alias a no-op). Also must store the
            # uppercased form, matching normalize()'s lookup convention, or
            # a freshly-registered alias can never be found again.
            existing_alias = session.exec(select(PredicateAlias).where(PredicateAlias.alias == normalized_alias)).first()
            if existing_alias:
                existing_alias.predicate_id = pred.id
                session.add(existing_alias)
            else:
                session.add(PredicateAlias(alias=normalized_alias, predicate_id=pred.id))
            
            session.commit()
        finally:
            if not self.session:
                session.close()
