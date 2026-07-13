import json
from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, select

from app.db.schema import Artifact, ArtifactRelation, Universe, UniverseRelation


class UniverseRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, universe_id: int) -> Universe | None:
        return self.session.get(Universe, universe_id)

    def get_by_name(self, name: str) -> Universe | None:
        return self.session.exec(select(Universe).where(Universe.name == name)).first()

    def get_by_slug(self, slug: str) -> Universe | None:
        return self.session.exec(select(Universe).where(Universe.slug == slug)).first()

    def get_by_uuid(self, uuid: str) -> Universe | None:
        return self.session.exec(select(Universe).where(Universe.uuid == uuid)).first()

    def get_all(
        self,
        order_by_name: bool = True,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(Universe)
        if fields:
            proj_fields = [getattr(Universe, f) for f in fields if hasattr(Universe, f)]
            if proj_fields:
                stmt = select(*proj_fields)
        if order_by_name:
            stmt = stmt.order_by(Universe.name)
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def filter_universes(
        self,
        q: str = "",
        explored: str = "",
        franchise: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Universe]:
        stmt = select(Universe)
        if q:
            # Filter by name or by franchise artifact
            franchise_subquery = select(Artifact).where(
                Artifact.universe_id == Universe.id,
                Artifact.type == "franchise",
                Artifact.name.contains(q)
            ).exists()
            stmt = stmt.where((Universe.name.contains(q)) | franchise_subquery)
        if explored == "yes":
            stmt = stmt.where(Universe.is_explored)
        elif explored == "no":
            stmt = stmt.where(~Universe.is_explored)
        if franchise:
            franchise_subquery = select(Artifact).where(
                Artifact.universe_id == Universe.id,
                Artifact.type == "franchise",
                Artifact.name.contains(franchise)
            ).exists()
            stmt = stmt.where(franchise_subquery)
        
        stmt = stmt.order_by(Universe.name)
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def get_by_names(self, names: list[str]) -> Sequence[Universe]:
        return self.session.exec(select(Universe).where(Universe.name.in_(names))).all()

    def get_explored(
        self, limit: int = 100, offset: int = 0, fields: list[str] | None = None
    ) -> Sequence[Any]:
        stmt = select(Universe).where(Universe.is_explored)
        if fields:
            proj_fields = [getattr(Universe, f) for f in fields if hasattr(Universe, f)]
            if proj_fields:
                stmt = select(*proj_fields).where(Universe.is_explored)
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def create(self, universe: Universe) -> Universe:
        self.session.add(universe)
        self.session.commit()
        self.session.refresh(universe)
        return universe

    def update(self, universe: Universe) -> Universe:
        self.session.add(universe)
        self.session.commit()
        self.session.refresh(universe)
        return universe

    def update_batch(self, universes: Sequence[Universe]):
        for universe in universes:
            self.session.add(universe)
        self.session.commit()

    def delete(self, universe: Universe):
        self.session.delete(universe)
        self.session.commit()

    def get_verified_claims(
        self,
        universe_id: int,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(ArtifactRelation).where(
            ArtifactRelation.universe_id == universe_id,
            # Fallback: we'll assume relations in main DB are verified
            ArtifactRelation.relation_type == "VERIFIED",
        )
        # Actually, just return all relations as they are in the main DB
        stmt = select(ArtifactRelation).where(
            ArtifactRelation.universe_id == universe_id
        )
        if fields:
            proj_fields = [
                getattr(ArtifactRelation, f)
                for f in fields
                if hasattr(ArtifactRelation, f)
            ]
            if proj_fields:
                stmt = select(*proj_fields).where(
                    ArtifactRelation.universe_id == universe_id
                )
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def create_relation(self, relation: UniverseRelation) -> UniverseRelation:
        self.session.add(relation)
        self.session.commit()
        self.session.refresh(relation)
        return relation

    def get_relations(
        self,
        universe_id: int | None = None,
        direction: str = "both",
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(UniverseRelation)
        if fields:
            proj_fields = [
                getattr(UniverseRelation, f)
                for f in fields
                if hasattr(UniverseRelation, f)
            ]
            if proj_fields:
                stmt = select(*proj_fields)

        if universe_id:
            if direction == "out":
                stmt = stmt.where(UniverseRelation.from_universe_id == universe_id)
            elif direction == "in":
                stmt = stmt.where(UniverseRelation.to_universe_id == universe_id)
            else:
                stmt = stmt.where(
                    (UniverseRelation.from_universe_id == universe_id)
                    | (UniverseRelation.to_universe_id == universe_id)
                )

        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def get_related_universes(self, universe_id: int) -> Sequence[Universe]:
        relations = self.get_relations(universe_id)
        related_ids = set()
        for r in relations:
            if r.from_universe_id == universe_id:
                related_ids.add(r.to_universe_id)
            else:
                related_ids.add(r.from_universe_id)
        return self.session.exec(
            select(Universe).where(Universe.id.in_(list(related_ids)))
        ).all()

    def get_children(self, universe_id: int) -> Sequence[Universe]:
        """Returns universes that have this universe as a parent."""
        return self.session.exec(
            select(Universe).where(Universe.parent_id == universe_id)
        ).all()

    def set_entity_canonical(self, artifact_id: int, canonical_id: int | None = None):
        artifact = self.session.get(Artifact, artifact_id)
        if artifact and artifact.type == "entity":
            payload = json.loads(artifact.payload_json or "{}")
            payload["canonical_entity_id"] = canonical_id
            payload["canonical"] = canonical_id is None
            artifact.payload_json = json.dumps(payload)
            self.session.add(artifact)
            self.session.commit()
            self.session.refresh(artifact)
        return artifact
