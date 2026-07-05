from typing import List, Optional, Sequence
from sqlmodel import Session, select, delete
from app.db.schema import Universe, Trait, Claim

class UniverseRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, universe_id: int) -> Optional[Universe]:
        return self.session.get(Universe, universe_id)

    def get_by_name(self, name: str) -> Optional[Universe]:
        return self.session.exec(select(Universe).where(Universe.name == name)).first()

    def get_all(self, order_by_name: bool = True) -> Sequence[Universe]:
        if order_by_name:
            return self.session.exec(select(Universe).order_by(Universe.name)).all()
        return self.session.exec(select(Universe)).all()

    def get_by_names(self, names: List[str]) -> Sequence[Universe]:
        return self.session.exec(select(Universe).where(Universe.name.in_(names))).all()

    def get_explored(self) -> Sequence[Universe]:
        return self.session.exec(select(Universe).where(Universe.is_explored == True)).all()

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

    def get_traits(self, universe_id: int) -> Sequence[Trait]:
        return self.session.exec(select(Trait).where(Trait.universe_id == universe_id)).all()

    def get_traits_by_universe_ids(self, universe_ids: List[int]) -> Sequence[Trait]:
        return self.session.exec(select(Trait).where(Trait.universe_id.in_(universe_ids))).all()

    def upsert_trait(self, trait: Trait) -> Trait:
        self.session.add(trait)
        self.session.commit()
        self.session.refresh(trait)
        return trait

    def get_verified_claims(self, universe_id: int) -> Sequence[Claim]:
        return self.session.exec(
            select(Claim).where(
                Claim.universe_scope == universe_id, 
                Claim.status == "VERIFIED"
            )
        ).all()
