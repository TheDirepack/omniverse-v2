from typing import List, Optional, Sequence, Dict, Any
from sqlmodel import Session
from app.db.session import engine
from app.db.schema import Universe, Trait, Claim
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
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_by_name(name)

    def get_universe_by_id(self, universe_id: int) -> Optional[Universe]:
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_by_id(universe_id)

    def get_all_universes(self) -> Sequence[Universe]:
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_all()

    def create_universe(self, name: str) -> Universe:
        with Session(engine) if not self.session else self.session as session:
            universe = Universe(name=name, summary=None, is_explored=False)
            repo = UniverseRepository(session)
            return repo.create(universe)

    def mark_explored(self, universe_id: int):
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = True
                repo.update(universe)

    def reset_explored(self, universe_id: int) -> bool:
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = False
                repo.update(universe)
                return True
            return False

    def reset_all_explored(self) -> int:
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universes = repo.get_all()
            count = 0
            for u in universes:
                if u.is_explored:
                    u.is_explored = False
                    repo.update(u)
                    count += 1
            return count

    def get_traits(self, universe_ids: Optional[str] = None) -> List[Dict[str, Any]]:
        with Session(engine) if not self.session else self.session as session:
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

    def get_verified_claims(self, universe_id: int) -> Sequence[Claim]:
        with Session(engine) if not self.session else self.session as session:
            return UniverseRepository(session).get_verified_claims(universe_id)

    def update_summary(self, universe_id: int, summary: str):
        with Session(engine) if not self.session else self.session as session:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.summary = summary
                repo.update(universe)

