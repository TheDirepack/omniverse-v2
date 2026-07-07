from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, func, select

from app.db.schema import Claim, InferenceRule, InferredClaim


class InferenceRepository:
    """Stateless repository: takes a live session per call, matching the
    fix in 5f45596 (services own session lifecycle, repos never hold one)."""

    def __init__(self, session: Session):
        self.session = session

    # --- Claim graph ---

    def get_claims_by_predicate(
        self,
        predicate: str,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        # Try finding by predicate_id first if it's been migrated
        from app.db.schema import Predicate

        # Check if any results exist for the migrated path
        exists_query = (
            select(Claim.id)
            .join(Predicate)
            .where(Predicate.canonical_name == predicate)
        )
        if self.session.exec(exists_query.limit(1)).first() is not None:
            stmt = (
                select(Claim)
                .join(Predicate, Claim.predicate_id == Predicate.id)
                .where(Predicate.canonical_name == predicate)
            )
            if fields:
                proj_fields = [getattr(Claim, f) for f in fields if hasattr(Claim, f)]
                if proj_fields:
                    stmt = (
                        select(*proj_fields)
                        .join(Predicate)
                        .where(Predicate.canonical_name == predicate)
                    )
            return self.session.exec(stmt.offset(offset).limit(limit)).all()
        else:
            # Fallback to deprecated string predicate column
            stmt = select(Claim).where(Claim.predicate == predicate)
            if fields:
                proj_fields = [getattr(Claim, f) for f in fields if hasattr(Claim, f)]
                if proj_fields:
                    stmt = select(*proj_fields).where(Claim.predicate == predicate)
            return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def get_claims_for_subject(
        self,
        subject_id: int,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(Claim).where(Claim.subject_id == subject_id)
        if fields:
            proj_fields = [getattr(Claim, f) for f in fields if hasattr(Claim, f)]
            if proj_fields:
                stmt = select(*proj_fields).where(Claim.subject_id == subject_id)
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def find_claim(
        self, subject_id: int, predicate: str, object_id: int
    ) -> Claim | None:
        from app.db.schema import Predicate

        # Try migrated path
        stmt = (
            select(Claim)
            .join(Predicate, Claim.predicate_id == Predicate.id)
            .where(
                Claim.subject_id == subject_id,
                Predicate.canonical_name == predicate,
                Claim.object_id == object_id,
            )
        )
        res = self.session.exec(stmt).first()
        if res:
            return res
        # Fallback
        return self.session.exec(
            select(Claim).where(
                Claim.subject_id == subject_id,
                Claim.predicate == predicate,
                Claim.object_id == object_id,
            )
        ).first()

    def find_claims_with_subject_predicate(
        self,
        subject_id: int,
        predicate: str,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        from app.db.schema import Predicate

        stmt = (
            select(Claim)
            .join(Predicate, Claim.predicate_id == Predicate.id)
            .where(
                Claim.subject_id == subject_id, Predicate.canonical_name == predicate
            )
        )
        if fields:
            proj_fields = [getattr(Claim, f) for f in fields if hasattr(Claim, f)]
            if proj_fields:
                stmt = (
                    select(*proj_fields)
                    .join(Predicate)
                    .where(
                        Claim.subject_id == subject_id,
                        Predicate.canonical_name == predicate,
                    )
                )

        res = self.session.exec(stmt.offset(offset).limit(limit)).all()
        if res:
            return res

        # Fallback
        stmt_fallback = select(Claim).where(
            Claim.subject_id == subject_id, Claim.predicate == predicate
        )
        if fields:
            proj_fields = [getattr(Claim, f) for f in fields if hasattr(Claim, f)]
            if proj_fields:
                stmt_fallback = select(*proj_fields).where(
                    Claim.subject_id == subject_id, Claim.predicate == predicate
                )
        return self.session.exec(stmt_fallback.offset(offset).limit(limit)).all()

    def frequent_predicate_pairs(
        self, min_count: int = 3
    ) -> list[tuple[str, str, int]]:
        """
        Find (predicate_1, predicate_2) pairs that co-occur via a shared
        intermediate entity: subject --p1--> mid --p2--> object.
        Used to surface candidates worth proposing an InferenceRule for.
        """
        from sqlalchemy import alias

        from app.db.schema import Predicate

        p1_alias = alias(Predicate.__table__, name="p1")
        p2_alias = alias(Predicate.__table__, name="p2")
        c1_table = Claim.__table__
        c2_alias = alias(Claim.__table__, name="c2")

        stmt = (
            select(
                func.coalesce(p1_alias.c.canonical_name, c1_table.c.predicate),
                func.coalesce(p2_alias.c.canonical_name, c2_alias.c.predicate),
                func.count(),
            )
            .select_from(
                c1_table.join(
                    c2_alias, c1_table.c.object_entity_id == c2_alias.c.subject_id
                )
                .outerjoin(p1_alias, c1_table.c.predicate_id == p1_alias.c.id)
                .outerjoin(p2_alias, c2_alias.c.predicate_id == p2_alias.c.id)
            )
            .group_by(
                func.coalesce(p1_alias.c.canonical_name, c1_table.c.predicate),
                func.coalesce(p2_alias.c.canonical_name, c2_alias.c.predicate),
            )
            .having(func.count() >= min_count)
        )
        rows = self.session.exec(stmt).all()
        return [(r[0], r[1], r[2]) for r in rows]

    # --- InferenceRule lifecycle ---

    def create_rule(self, rule: InferenceRule) -> InferenceRule:
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def update_rule(self, rule: InferenceRule) -> InferenceRule:
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return rule

    def get_rule(self, rule_id: int) -> InferenceRule | None:
        return self.session.get(InferenceRule, rule_id)

    def get_rules_by_status(self, status: str) -> Sequence[InferenceRule]:
        return self.session.exec(
            select(InferenceRule).where(InferenceRule.status == status)
        ).all()

    def get_approved_rules(self) -> Sequence[InferenceRule]:
        return self.session.exec(
            select(InferenceRule).where(
                InferenceRule.human_approved == True,  # noqa: E712
                InferenceRule.rule_type == "compose",
            )
        ).all()

    def existing_rule_for_pair(
        self, predicate_1: str, predicate_2: str
    ) -> InferenceRule | None:
        return self.session.exec(
            select(InferenceRule).where(
                InferenceRule.predicate_1 == predicate_1,
                InferenceRule.predicate_2 == predicate_2,
            )
        ).first()

    # --- InferredClaim ---

    def create_inferred_claim(self, ic: InferredClaim) -> InferredClaim:
        self.session.add(ic)
        return ic

    def add_inferred_claim_paths(self, inferred_claim_id: int, claim_ids: list[int]):
        from app.db.schema import InferredClaimPath

        for i, claim_id in enumerate(claim_ids):
            self.session.add(
                InferredClaimPath(
                    inferred_claim_id=inferred_claim_id, claim_id=claim_id, hop_index=i
                )
            )

    def get_inferred_claim_paths(self, inferred_claim_id: int) -> Sequence[int]:
        from app.db.schema import InferredClaimPath

        return self.session.exec(
            select(InferredClaimPath.claim_id)
            .where(InferredClaimPath.inferred_claim_id == inferred_claim_id)
            .order_by(InferredClaimPath.hop_index)
        ).all()

    def get_inferred_claim(
        self, subject_id: int, predicate: str, object_id: int
    ) -> InferredClaim | None:
        return self.session.exec(
            select(InferredClaim).where(
                InferredClaim.subject_id == subject_id,
                InferredClaim.predicate == predicate,
                InferredClaim.object_id == object_id,
            )
        ).first()

    def get_unreviewed_contradictions(
        self, limit: int = 100, offset: int = 0, fields: list[str] | None = None
    ) -> Sequence[Any]:
        stmt = select(InferredClaim).where(
            InferredClaim.contradicts_claim_id.is_not(None),
            InferredClaim.reviewed == False,  # noqa: E712
        )
        if fields:
            proj_fields = [
                getattr(InferredClaim, f) for f in fields if hasattr(InferredClaim, f)
            ]
            if proj_fields:
                stmt = select(*proj_fields).where(
                    InferredClaim.contradicts_claim_id.is_not(None),
                    InferredClaim.reviewed == False,  # noqa: E712
                )
        return self.session.exec(stmt.offset(offset).limit(limit)).all()
