import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.db.schema import Universe, UniverseRelation
from app.db.session import engine
from app.repositories.universe import UniverseRepository


class UniverseService:
    def __init__(self, session: Session | None = None):
        self.session = session
        self._repo: UniverseRepository | None = None

    @property
    def repo(self) -> UniverseRepository:
        """Lazily-created, cached repo bound to a dedicated session held for
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

    def get_universe(self, name: str) -> Universe | None:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_name(name)
        finally:
            if not self.session:
                session.close()

    def get_universe_by_id(self, universe_id: int) -> Universe | None:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_id(universe_id)
        finally:
            if not self.session:
                session.close()

    def get_universe_by_uuid(self, uuid: str) -> Universe | None:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_uuid(uuid)
        finally:
            if not self.session:
                session.close()

    def get_all_universes(
        self, limit: int = 100, offset: int = 0, fields: list[str] | None = None
    ) -> Sequence[Any]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_all(
                limit=limit, offset=offset, fields=fields
            )
        finally:
            if not self.session:
                session.close()

    def _generate_slug(self, repo: UniverseRepository, name: str) -> str:
        base_slug = name.lower().replace(" ", "_")
        slug = base_slug
        counter = 1
        while repo.get_by_slug(slug):
            slug = f"{base_slug}_{counter}"
            counter += 1
        return slug

    def create_universe(
        self,
        name: str,
        franchise: str | None = None,
        category: str | None = None,
        continuity: str | None = None,
        era: str | None = None,
        parent_id: int | None = None,
    ) -> Universe:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            slug = self._generate_slug(repo, name)
            universe = Universe(
                name=name,
                slug=slug,
                franchise=franchise,
                category=category,
                continuity=continuity,
                era=era,
                parent_id=parent_id,
                summary=None,
                is_explored=False,
            )
            res = repo.create(universe)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def import_from_registry(self, world_id: str) -> Universe | None:
        json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
        if not json_path.exists():
            return None
        with open(json_path) as f:
            entries = json.load(f)
        match = next((e for e in entries if e.get("id") == world_id), None)
        if not match:
            return None

        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            existing_by_slug = repo.get_by_slug(match["id"])
            if existing_by_slug:
                return existing_by_slug

            existing_by_name = repo.get_by_name(match["name"])
            if existing_by_name:
                return existing_by_name

            parent_id = None
            parent_ref = match.get("parent")
            if parent_ref:
                parent = repo.get_by_slug(parent_ref)
                if parent and parent.id is not None:
                    parent_id = parent.id

            universe = Universe(
                slug=match["id"],
                name=match["name"],
                franchise=match.get("franchise"),
                category=match.get("category"),
                continuity=match.get("continuity"),
                era=match.get("era"),
                parent_id=parent_id,
                summary=None,
                is_explored=False,
            )
            res = repo.create(universe)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def import_all_from_registry(self) -> tuple[int, int]:
        json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
        if not json_path.exists():
            return 0, 0
        with open(json_path) as f:
            entries = json.load(f)

        session = self.session or Session(engine)
        imported = 0
        skipped = 0
        try:
            existing_slugs = {r for r in session.exec(select(Universe.slug)).all() if r}
            existing_names = {r for r in session.exec(select(Universe.name)).all()}

            parent_map: dict[str, int] = {}
            for entry in entries:
                slug = entry["id"]
                name = entry["name"]
                if slug in existing_slugs or name in existing_names:
                    skipped += 1
                    continue

                parent_id = None
                parent_ref = entry.get("parent")
                if parent_ref:
                    if parent_ref in parent_map:
                        parent_id = parent_map[parent_ref]
                    elif parent_ref in existing_slugs:
                        parent_id = session.exec(
                            select(Universe.id).where(Universe.slug == parent_ref)
                        ).first()

                universe = Universe(
                    slug=slug,
                    name=name,
                    franchise=entry.get("franchise"),
                    category=entry.get("category"),
                    continuity=entry.get("continuity"),
                    era=entry.get("era"),
                    parent_id=parent_id,
                    summary=None,
                    is_explored=False,
                )
                session.add(universe)
                existing_slugs.add(slug)
                existing_names.add(name)
                imported += 1

            session.commit()
            return imported, skipped
        finally:
            if not self.session:
                session.close()

    def find_duplicates(
        self, name: str, threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            all_worlds = repo.get_all()
            candidates = []
            name_lower = name.lower()
            for w in all_worlds:
                w_name_lower = w.name.lower() if w.name else ""
                similarity = self._name_similarity(name_lower, w_name_lower)
                if similarity >= threshold:
                    candidates.append({
                        "id": w.id,
                        "uuid": w.uuid,
                        "name": w.name,
                        "franchise": w.franchise,
                        "similarity": similarity,
                    })
            return sorted(candidates, key=lambda x: x["similarity"], reverse=True)
        finally:
            if not self.session:
                session.close()

    def _name_similarity(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        if a in b or b in a:
            return 0.85
        a_parts = set(a.replace("/", " ").replace("-", " ").split())
        b_parts = set(b.replace("/", " ").replace("-", " ").split())
        if not a_parts or not b_parts:
            return 0.0
        intersection = a_parts & b_parts
        return len(intersection) / max(len(a_parts), len(b_parts))

    def merge_worlds(self, keep_id: int, merge_id: int) -> dict[str, Any]:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            keep = repo.get_by_id(keep_id)
            merge = repo.get_by_id(merge_id)
            if not keep or not merge:
                return {"status": "error", "message": "One or both worlds not found"}

            from app.db.schema import Claim, Entity

            entities = session.exec(
                select(Entity).where(Entity.universe_id == merge_id)
            ).all()
            for e in entities:
                existing = session.exec(
                    select(Entity).where(
                        Entity.universe_id == keep_id,
                        Entity.name == e.name,
                    )
                ).first()
                if not existing:
                    e.universe_id = keep_id
                    session.add(e)

            claims = session.exec(
                select(Claim).where(Claim.universe_scope == merge_id)
            ).all()
            for c in claims:
                existing = session.exec(
                    select(Claim).where(
                        Claim.subject_id.in_(
                            select(Entity.id).where(Entity.universe_id == keep_id)
                        ),
                        Claim.predicate == c.predicate,
                        Claim.object_literal == c.object_literal,
                    )
                ).first()
                if not existing:
                    c.universe_scope = keep_id
                    session.add(c)

            repo.delete(merge)
            session.commit()
            return {"status": "success", "keep_id": keep_id, "merge_id": merge_id}
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
                session.commit()
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
                session.commit()
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
            if count > 0:
                session.commit()
            return count
        finally:
            if not self.session:
                session.close()

    def get_verified_claims(
        self,
        universe_id: int,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_verified_claims(
                universe_id, limit=limit, offset=offset, fields=fields
            )
        finally:
            if not self.session:
                session.close()

    def get_claims(
        self,
        universe_ids: str | None = None,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        session = self.session or Session(engine)
        try:
            from app.db.schema import Claim, Universe

            query = select(Claim).join(Universe)
            if universe_ids and universe_ids != "None":
                ids = [int(i) for i in universe_ids.split(",") if i.strip().isdigit()]
                if ids:
                    query = query.where(Claim.universe_scope.in_(ids))

            if fields:
                valid_fields = [f for f in fields if hasattr(Claim, f)]
                proj_fields = [getattr(Claim, f) for f in valid_fields]
                if proj_fields:
                    query = select(*proj_fields).join(Universe)
                    if universe_ids and universe_ids != "None":
                        ids = [
                            int(i)
                            for i in universe_ids.split(",")
                            if i.strip().isdigit()
                        ]
                        if ids:
                            query = query.where(Claim.universe_scope.in_(ids))

            results = session.exec(query.offset(offset).limit(limit)).all()
            if fields:
                valid_fields = [f for f in fields if hasattr(Claim, f)]
                return [
                    dict(zip(valid_fields, r))
                    if isinstance(r, tuple)
                    else {f: getattr(r, f, None) for f in valid_fields}
                    for r in results
                ]
            return results
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
                session.commit()
        finally:
            if not self.session:
                session.close()

    def create_universe_relation(
        self, from_id: int, to_id: int, rel_type: str, description: str | None = None
    ) -> UniverseRelation:
        session = self.session or Session(engine)
        try:
            relation = UniverseRelation(
                from_universe_id=from_id,
                to_universe_id=to_id,
                relation_type=rel_type,
                description=description,
            )
            res = UniverseRepository(session).create_relation(relation)
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def get_universe_relations(
        self,
        universe_id: int,
        direction: str = "both",
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_relations(
                universe_id, direction, limit=limit, offset=offset, fields=fields
            )
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

    def set_entity_canonical(self, entity_id: int, canonical_id: int | None = None):
        session = self.session or Session(engine)
        try:
            res = UniverseRepository(session).set_entity_canonical(
                entity_id, canonical_id
            )
            session.commit()
            return res
        finally:
            if not self.session:
                session.close()

    def delete_universe(self, universe_id: int):
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                repo.delete(universe)
                session.commit()
        finally:
            if not self.session:
                session.close()

    def close(self):
        """Closes the internal session if lazily created."""
        if self._repo and not self.session:
            self._repo.session.close()
            self._repo = None
