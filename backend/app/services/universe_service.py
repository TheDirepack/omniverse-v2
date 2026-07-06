from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import Universe, Claim, UniverseRelation
from app.repositories.universe import UniverseRepository

class UniverseService:
    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self._repo: Optional[UniverseRepository] = None

    @property
    def repo(self) -> UniverseRepository:
        """
        Lazily-created, cached repo bound to a dedicated session held for
        this UniverseService instance's lifetime. Restores the .repo access
        pattern that several call sites across the pipeline (nodes.py,
        summarizer.py, runs.py, and the workflow modules) depend on to make
        multiple sequential repo calls within one execution -- this was
        removed in an earlier session-leak refactor without updating those
        call sites, causing "'UniverseService' object has no attribute
        'repo'" crashes at runtime.

        Deliberately independent from self.session/the `with Session(engine)
        if not self.session else self.session as session:` pattern used by
        every method below -- those open and close a short-lived session per
        call, so sharing a session with .repo would close it out from under
        callers still using .repo afterward. All current .repo call sites
        instantiate UniverseService() with no session argument, so this
        stays fully decoupled from that path.

        NOTE: this does re-introduce a held-open session for the object's
        lifetime (same tradeoff TieringService already has) rather than the
        fully session-scoped pattern used elsewhere in this class. A fuller
        rewrite of all 10 call sites to short-lived, purpose-built service
        methods (matching get_universe/get_all_universes/etc. below) would
        be the cleaner long-term fix, but touches 6 files across the whole
        pipeline and is out of scope for this crash fix.
        """
        if self._repo is None:
            self._repo = UniverseRepository(self.session or Session(engine))
        return self._repo

    def _get_repo(self) -> UniverseRepository:
        # Kept for backward compatibility with any existing callers;
        # delegates to the same cached instance as the .repo property so
        # there's only ever one repo/session per UniverseService instance.
        return self.repo

    def get_universe(self, name: str) -> Optional[Universe]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_name(name)
        finally:
            if not self.session:
                session.close()

    def get_universe_by_id(self, universe_id: int) -> Optional[Universe]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_id(universe_id)
        finally:
            if not self.session:
                session.close()

    def get_all_universes(self) -> Sequence[Universe]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_all()
        finally:
            if not self.session:
                session.close()

    def create_universe(self, name: str) -> Universe:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            base_slug = name.lower().replace(" ", "_")
            slug = base_slug
            counter = 1
            while repo.get_by_slug(slug):
                slug = f"{base_slug}_{counter}"
                counter += 1
            
            universe = Universe(name=name, slug=slug, summary=None, is_explored=False)
            return repo.create(universe)
        finally:
            if not self.session:
                session.close()

    def mark_explored(self, universe_id: int):
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = True
                repo.update(universe)
        finally:
            if not self.session:
                session.close()

    def reset_explored(self, universe_id: int) -> bool:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = False
                repo.update(universe)
                return True
            return False
        finally:
            if not self.session:
                session.close()

    def reset_all_explored(self) -> int:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            universes = repo.get_all()
            count = 0
            for u in universes:
                if u.is_explored:
                    u.is_explored = False
                    repo.update(u)
                    count += 1
            return count
        finally:
            if not self.session:
                session.close()

    def get_traits(self, universe_ids: Optional[str] = None) -> List[Dict[str, Any]]:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            if universe_ids:
                ids = [int(id_str) for id_str in universe_ids.split(",") if id_str.strip()]
                traits = repo.get_traits_by_universe_ids(ids)
            else:
                all_universes = repo.get_all()
                traits = []
                for u in all_universes:
                    traits.extend(repo.get_traits(u.id))
            return [t.model_dump() for t in traits]
        finally:
            if not self.session:
                session.close()

    def get_verified_claims(self, universe_id: int) -> Sequence[Claim]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_verified_claims(universe_id)
        finally:
            if not self.session:
                session.close()

    def update_summary(self, universe_id: int, summary: str):
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.summary = summary
                repo.update(universe)
        finally:
            if not self.session:
                session.close()

    def create_universe_relation(self, from_id: int, to_id: int, rel_type: str, description: Optional[str] = None) -> UniverseRelation:
        session = self.session or Session(engine)
        try:
            relation = UniverseRelation(from_universe_id=from_id, to_universe_id=to_id, relation_type=rel_type, description=description)
            return UniverseRepository(session).create_relation(relation)
        finally:
            if not self.session:
                session.close()

    def get_universe_relations(self, universe_id: int, direction: str = "both") -> Sequence[UniverseRelation]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_relations(universe_id, direction)
        finally:
            if not self.session:
                session.close()

    def get_related_universes(self, universe_id: int) -> Sequence[Universe]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_related_universes(universe_id)
        finally:
            if not self.session:
                session.close()

    def set_entity_canonical(self, entity_id: int, canonical_id: Optional[int] = None):
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).set_entity_canonical(entity_id, canonical_id)
        finally:
            if not self.session:
                session.close()

    def close(self):
        """Closes the internal session if it was lazily created."""
        if self._repo and not self.session:
            self._repo.session.close()
            self._repo = None

