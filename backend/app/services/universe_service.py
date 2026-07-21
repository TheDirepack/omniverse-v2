import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sqlmodel import Session, delete, select

from app.db.schema import (
    Anomaly,
    Artifact,
    ArtifactRelation,
    ArtifactVersion,
    Evidence,
    EvidenceChunk,
    Universe,
    UniverseRelation,
    WorldTier,
)
from app.db.session import engine
from app.repositories.universe import UniverseRepository

logger = logging.getLogger(__name__)


class UniverseService:
    def __init__(self, session: Session | None = None):
        self.session = session
        self._repo = None

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

    def get_universe_by_slug(self, slug: str) -> Universe | None:
        session = self.session or Session(engine)
        try:
            return UniverseRepository(session).get_by_slug(slug)
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
        self, limit: int = 100, offset: int = 0, fields: list[str] | None = None, count_only: bool = False
    ) -> int | Sequence[Any]:
        if count_only:
            session = self.session or Session(engine)
            try:
                from sqlmodel import func, select
                from app.db.schema import Universe
                result = session.exec(select(func.count()).select_from(Universe))
                return result.one()
            finally:
                if not self.session:
                    session.close()
        limit = min(max(limit, 1), 1000)
        offset = max(offset, 0)
        session = self.session or Session(engine)
        try:
            results = UniverseRepository(session).get_all(
                limit=limit, offset=offset, fields=fields
            )
            if fields:
                valid_fields = [f for f in fields if hasattr(Universe, f)]
                return [
                    {f: getattr(r, f, None) for f in valid_fields}
                    for r in results
                ]
            return results
        finally:
            if not self.session:
                session.close()

    def filter_universes(
        self,
        q: str = "",
        explored: str = "",
        franchise: str = "",
        limit: int = 5000,
        offset: int = 0,
    ) -> list[Universe]:
        session = self.session or Session(engine)
        try:
            return list(UniverseRepository(session).filter_universes(
                q=q, explored=explored, franchise=franchise, limit=limit, offset=offset
            ))
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
        import re
        base_slug = re.sub(r'[^a-z0-9_]', '', name.lower().replace(" ", "_"))
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
                parent_id=parent_id,
                summary=None,
                is_explored=False,
                franchise=franchise,
                category=category,
                continuity=continuity,
                era=era,
            )
            session.add(universe)
            session.flush()

            # Create artifacts for metadata
            from app.db.schema import Artifact, ArtifactRelation

            world_art = Artifact(universe_id=universe.id, type="world", name=name)
            session.add(world_art)
            session.flush()

            metadata = {
                "franchise": franchise,
                "category": category,
                "continuity": continuity,
                "era": era,
            }

            for m_type, m_value in metadata.items():
                if m_value:
                    m_art = Artifact(universe_id=universe.id, type=m_type, name=m_value)
                    session.add(m_art)
                    session.flush()

                    rel = ArtifactRelation(
                        universe_id=universe.id,
                        from_artifact_id=world_art.id,
                        to_artifact_id=m_art.id,
                        relation_type="PART_OF",
                    )
                    session.add(rel)

            session.commit()
            session.refresh(universe)
            return universe
        finally:
            if not self.session:
                session.close()

    def import_from_registry(self, world_id: str) -> Universe | None:
        try:
            json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
            logger.info(f"Checking registry file: {json_path}, exists: {json_path.exists()}")
            if not json_path.exists():
                return None
            with json_path.open() as f:
                entries = json.load(f)
            match = next((e for e in entries if e.get("id") == world_id), None)
            logger.info(f"Registry lookup for {world_id}: {match}")
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
        except Exception:
            logger.exception("Failed to import world %s from registry", world_id)
            raise

    def import_all_from_registry(self) -> tuple[int, int]:
        try:
            json_path = Path(__file__).parent.parent / "db" / "default_worlds.json"
            if not json_path.exists():
                return 0, 0
            with json_path.open() as f:
                entries = json.load(f)

            session = self.session or Session(engine)
            imported = 0
            skipped = 0
            try:
                existing_slugs = set(filter(None, session.exec(select(Universe.slug)).all()))
                existing_names = set(session.exec(select(Universe.name)).all())

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
                            result = session.exec(
                                select(Universe.id).where(Universe.slug == parent_ref)
                            ).first()
                            # Ensure we get a valid int, not a tuple (SingleResult returns tuples)
                            if isinstance(result, tuple):
                                parent_id = result[0] if result else None
                            else:
                                parent_id = result

                    universe = Universe(
                        slug=slug,
                        name=name,
                        parent_id=parent_id,
                        summary=None,
                        is_explored=False,
                    )
                    session.add(universe)
                    session.flush()
                    parent_map[slug] = universe.id

                    existing_slugs.add(slug)
                    existing_names.add(name)
                    imported += 1

                session.commit()
                return imported, skipped
            finally:
                if not self.session:
                    session.close()
        except Exception:
            logger.exception("Failed to import all worlds from registry")
            raise

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
            if keep_id == merge_id:
                return {"status": "error", "message": "Cannot merge a world with itself"}
            if not keep or not merge:
                return {"status": "error", "message": "One or both worlds not found"}

            # 1. Map artifacts and reassign them
            artifact_map = {}  # merge_art_id -> keep_art_id
            artifacts = session.exec(
                select(Artifact).where(Artifact.universe_id == merge_id)
            ).all()
            for a in artifacts:
                # Only merge "entity" type artifacts by name
                if a.type == "entity":
                    existing = session.exec(
                        select(Artifact).where(
                            Artifact.universe_id == keep_id,
                            Artifact.type == "entity",
                            Artifact.name == a.name,
                        )
                    ).first()
                    if existing:
                        # Merge evidence_refs as set union
                        ref_keep = json.loads(existing.evidence_refs or "[]")
                        ref_merge = json.loads(a.evidence_refs or "[]")
                        union_refs = sorted(set(ref_keep) | set(ref_merge))
                        existing.evidence_refs = json.dumps(union_refs)
                        existing.support_count = len(union_refs)
                        session.add(existing)

                        # Re-parent ArtifactVersion records and shift versions
                        versions = session.exec(
                            select(ArtifactVersion)
                            .where(ArtifactVersion.artifact_id == a.id)
                            .order_by(ArtifactVersion.version.asc())
                        ).all()

                        if versions:
                            max_ver_keep = session.exec(
                                select(ArtifactVersion.version)
                                .where(ArtifactVersion.artifact_id == existing.id)
                                .order_by(ArtifactVersion.version.desc())
                            ).first()

                            offset = (max_ver_keep or 0)
                            for v in versions:
                                v.artifact_id = existing.id
                                v.version = v.version + offset
                                session.add(v)

                        artifact_map[a.id] = existing.id
                    else:
                        a.universe_id = keep_id
                        session.add(a)
                        session.flush()
                        artifact_map[a.id] = a.id
                else:
                    # For other artifact types, just reassign universe
                    a.universe_id = keep_id
                    session.add(a)
                    session.flush()
                    artifact_map[a.id] = a.id

            # 2. Reassign relations and deduplicate
            relations = session.exec(
                select(ArtifactRelation).where(ArtifactRelation.universe_id == merge_id)
            ).all()
            for r in relations:
                new_from = artifact_map.get(r.from_artifact_id, r.from_artifact_id)
                new_to = artifact_map.get(r.to_artifact_id, r.to_artifact_id)

                # Check for duplicate relation
                dup_query = select(ArtifactRelation).where(
                    ArtifactRelation.universe_id == keep_id,
                    ArtifactRelation.from_artifact_id == new_from,
                    ArtifactRelation.to_artifact_id == new_to,
                    ArtifactRelation.relation_type == r.relation_type,
                )

                existing = session.exec(dup_query).first()
                if not existing:
                    r.from_artifact_id = new_from
                    r.to_artifact_id = new_to
                    r.universe_id = keep_id
                    session.add(r)
                else:
                    # In the new system, we don't have a superseded_by for relations,
                    # just let the duplicate be deleted or ignored.
                    session.delete(r)

            # 3. Reassign other child records
            # WorldTier
            tiers = (
                session.exec(select(WorldTier).where(WorldTier.universe_id == merge_id))
                .all()
            )
            for t in tiers:
                t.universe_id = keep_id
                session.add(t)

            # Anomaly
            anoms = (
                session.exec(select(Anomaly).where(Anomaly.universe_id == merge_id))
                .all()
            )
            for an in anoms:
                an.universe_id = keep_id
                session.add(an)

            # Evidence
            evs = (
                session.exec(select(Evidence).where(Evidence.universe_id == merge_id))
                .all()
            )
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

    def toggle_explored(self, universe_id: int) -> bool:
        session = self.session or Session(engine)
        try:
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                universe.is_explored = not universe.is_explored
                repo.update(universe)
                session.commit()
                return True
            return False
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
        _fields: list[str] | None = None,
    ) -> Sequence[Any]:
        session = self.session or Session(engine)
        try:
            # Using ArtifactRelation for verified claims
            stmt = select(ArtifactRelation).where(
                ArtifactRelation.universe_id == universe_id,
                # we can't easily check verification_status on the relation,
                # but we can join to the 'to' artifact to see if it's verified
                # or just assume relations are verified if they exist in main DB
            )
            # For now, just return all relations for that universe
            return session.exec(stmt.offset(offset).limit(limit)).all()
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
            query = select(ArtifactRelation).join(Universe)
            if universe_ids and universe_ids != "None":
                ids = [int(i) for i in universe_ids.split(",") if i.strip().isdigit()]
                if ids:
                    query = query.where(ArtifactRelation.universe_id.in_(ids))

            if fields:
                valid_fields = [f for f in fields if hasattr(ArtifactRelation, f)]
                proj_fields = [getattr(ArtifactRelation, f) for f in valid_fields]
                if proj_fields:
                    query = select(*proj_fields).join(Universe)
                    if universe_ids and universe_ids != "None":
                        ids = [
                            int(i)
                            for i in universe_ids.split(",")
                            if i.strip().isdigit()
                        ]
                        if ids:
                            query = query.where(ArtifactRelation.universe_id.in_(ids))

            results = session.exec(query.offset(offset).limit(limit)).all()
            if fields:
                valid_fields = [f for f in fields if hasattr(Universe, f)]
                return [
                    {f: getattr(r, f, None) for f in valid_fields}
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
            # Order: Relations -> Artifacts -> WorldTier
            # -> Anomaly -> Relation -> EvidenceChunk -> Evidence -> Universe
            # 1. ArtifactRelations and Artifacts
            session.exec(
                delete(ArtifactRelation).where(ArtifactRelation.universe_id == universe_id)
            )
            session.exec(delete(Artifact).where(Artifact.universe_id == universe_id))

            # 3. WorldTiers
            session.exec(delete(WorldTier).where(WorldTier.universe_id == universe_id))

            # 4. Anomalies
            session.exec(delete(Anomaly).where(Anomaly.universe_id == universe_id))

            # 5. UniverseRelations
            session.exec(
                delete(UniverseRelation).where(
                    (UniverseRelation.from_universe_id == universe_id) |
                    (UniverseRelation.to_universe_id == universe_id)
                )
            )

            # 6. EvidenceChunks (via Evidence)
            evidence = (
                session.exec(select(Evidence).where(Evidence.universe_id == universe_id))
                .all()
            )
            evidence_ids = [ev.id for ev in evidence]
            if evidence_ids:
                session.exec(
                    delete(EvidenceChunk).where(EvidenceChunk.evidence_id.in_(evidence_ids))
                )

            # 7. Evidence
            session.exec(delete(Evidence).where(Evidence.universe_id == universe_id))

            # 8. Finally, the Universe
            repo = UniverseRepository(session)
            universe = repo.get_by_id(universe_id)
            if universe:
                repo.delete(universe)

            session.commit()
        finally:
            if not self.session:
                session.close()

    def close(self):
        """No-op — kept for backward compatibility."""

    def get_universe_metadata(self, universe_id: int) -> dict[str, str | None]:
        session = self.session or Session(engine)
        try:
            from sqlmodel import select

            from app.db.schema import Artifact
            stmt = select(Artifact).where(Artifact.universe_id == universe_id)
            artifacts = session.exec(stmt).all()

            metadata = {
                "franchise": None,
                "continuity": None,
                "era": None,
                "category": None,
            }
            for a in artifacts:
                if a.type in metadata:
                    metadata[a.type] = a.name
            return metadata
        finally:
            if not self.session:
                session.close()
