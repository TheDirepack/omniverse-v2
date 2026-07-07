from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, select

from app.db.schema import Claim, Entity, Universe, UniverseRelation


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
        stmt = select(Claim).where(
            Claim.universe_scope == universe_id, Claim.status == "VERIFIED"
        )
        if fields:
            proj_fields = [getattr(Claim, f) for f in fields if hasattr(Claim, f)]
            if proj_fields:
                stmt = select(*proj_fields).where(
                    Claim.universe_scope == universe_id, Claim.status == "VERIFIED"
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

    def set_entity_canonical(self, entity_id: int, canonical_id: int | None = None):
        entity = self.session.get(Entity, entity_id)
        if entity:
            entity.canonical_entity_id = canonical_id
            entity.canonical = canonical_id is None
            self.session.add(entity)
            self.session.commit()
            self.session.refresh(entity)
        return entity
