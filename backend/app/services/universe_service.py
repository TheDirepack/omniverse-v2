import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlmodel import Session, select, delete

from app.db.schema import Universe, UniverseRelation, Claim, Entity, EntityAlias, WorldTier, Anomaly, Evidence, EvidenceChunk, InferredClaim
from app.db.session import engine
from app.repositories.universe import UniverseRepository


class UniverseService:
    def __init__(self, session: Session | None = None):
        self.session = session

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

    def get_children(self, universe_id: int) -> Sequence[Universe]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_children(universe_id)
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

    def get_by_names(self, names: list[str]) -> Sequence[Universe]:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_names(names)
        finally:
            if not self.session:
                session.close()

    def update_batch(self, universes: Sequence[Universe]):
        session = self.session or Session(engine)
        try:
            UniverseRepository(session).update_batch(universes)
            session.commit()
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

            # 1. Map entities and reassign them
            entity_map = {}  # merge_ent_id -> keep_ent_id
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
                if existing:
                    entity_map[e.id] = existing.id
                else:
                    e.universe_id = keep_id
                    session.add(e)
                    session.flush()
                    entity_map[e.id] = e.id

            # 2. Reassign claims and deduplicate
            claims = session.exec(
                select(Claim).where(Claim.universe_scope == merge_id)
            ).all()
            for c in claims:
                new_sub_id = entity_map.get(c.subject_id, c.subject_id)
                new_obj_ent_id = entity_map.get(c.object_entity_id, c.object_entity_id) if c.object_entity_id else None
                
                if c.object_entity_id:
                    dup_query = select(Claim).where(
                        Claim.universe_scope == keep_id,
                        Claim.subject_id == new_sub_id,
                        Claim.predicate == c.predicate,
                        Claim.object_entity_id == new_obj_ent_id,
                        Claim.object_literal.is_(None)
                    )
                else:
                    dup_query = select(Claim).where(
                        Claim.universe_scope == keep_id,
                        Claim.subject_id == new_sub_id,
                        Claim.predicate == c.predicate,
                        Claim.object_literal == c.object_literal,
                        Claim.object_entity_id.is_(None)
                    )
                
                existing = session.exec(dup_query).first()
                if not existing:
                    c.subject_id = new_sub_id
                    c.object_entity_id = new_obj_ent_id
                    c.universe_scope = keep_id
                    session.add(c)
                else:
                    c.superseded_by = existing.id
                    session.add(c)

            # 3. Reassign other child records
            # EntityAlias
            aliases = session.exec(select(EntityAlias).where(EntityAlias.universe_id == merge_id)).all()
            for a in aliases:
                a.universe_id = keep_id
                session.add(a)
            
            # WorldTier
            tiers = session.exec(select(WorldTier).where(WorldTier.universe_id == merge_id)).all()
            for t in tiers:
                t.universe_id = keep_id
                session.add(t)
            
            # Anomaly
            anoms = session.exec(select(Anomaly).where(Anomaly.universe_id == merge_id)).all()
            for an in anoms:
                an.universe_id = keep_id
                session.add(an)
            
            # Evidence
            evs = session.exec(select(Evidence).where(Evidence.universe_id == merge_id)).all()
            for ev in evs:
                ev.universe_id = keep_id
                session.add(ev)

            # UniverseRelation
            rels = session.exec(
                select(UniverseRelation).where(
                    (UniverseRelation.from_universe_id == merge_id) | 
                    (UniverseRelation.to_universe_id == merge_id)
                )
            ).all()
            for r in rels:
                if r.from_universe_id == merge_id:
                    r.from_universe_id = keep_id
                if r.to_universe_id == merge_id:
                    r.to_universe_id = keep_id
                session.add(r)

            # 4. Delete the merged universe
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
            # Cascading cleanup to prevent IntegrityError
            # Order: InferredClaim -> Claim -> EntityAlias -> Entity -> WorldTier -> Anomaly -> Relation -> EvidenceChunk -> Evidence -> Universe
            
            # 1. InferredClaims referencing entities of this universe
            entities = session.exec(select(Entity).where(Entity.universe_id == universe_id)).all()
            entity_ids = [e.id for e in entities]
            if entity_ids:
                session.exec(
                    delete(InferredClaim).where(
                        (InferredClaim.subject_id.in_(entity_ids)) | 
                        (InferredClaim.object_id.in_(entity_ids))
                    )
                )
            
            # 2. Claims
            session.exec(delete(Claim).where(Claim.universe_scope == universe_id))
            
            # 3. EntityAlias
            session.exec(delete(EntityAlias).where(EntityAlias.universe_id == universe_id))
            
            # 4. Entities
            session.exec(delete(Entity).where(Entity.universe_id == universe_id))
            
            # 5. WorldTiers
            session.exec(delete(WorldTier).where(WorldTier.universe_id == universe_id))
            
            # 6. Anomalies
            session.exec(delete(Anomaly).where(Anomaly.universe_id == universe_id))
            
            # 7. UniverseRelations
            session.exec(
                delete(UniverseRelation).where(
                    (UniverseRelation.from_universe_id == universe_id) | 
                    (UniverseRelation.to_universe_id == universe_id)
                )
            )
            
            # 8. EvidenceChunks (via Evidence)
            evidence = session.exec(select(Evidence).where(Evidence.universe_id == universe_id)).all()
            evidence_ids = [ev.id for ev in evidence]
            if evidence_ids:
                session.exec(delete(EvidenceChunk).where(EvidenceChunk.evidence_id.in_(evidence_ids)))
            
            # 9. Evidence
            session.exec(delete(Evidence).where(Evidence.universe_id == universe_id))
            
            # 10. Finally, the Universe
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
