from typing import List, Optional, Sequence, Tuple
from sqlmodel import Session, select, func
from app.db.schema import Claim, InferenceRule, InferredClaim, Entity


class InferenceRepository:
    """Stateless repository: takes a live session per call, matching the
    fix in 5f45596 (services own session lifecycle, repos never hold one)."""

    def __init__(self, session: Session):
        self.session = session

    # --- Claim graph ---

    def get_claims_by_predicate(self, predicate: str) -> Sequence[Claim]:
        return self.session.exec(select(Claim).where(Claim.predicate == predicate)).all()

    def get_claims_for_subject(self, subject_id: int) -> Sequence[Claim]:
        return self.session.exec(select(Claim).where(Claim.subject_id == subject_id)).all()

    def find_claim(self, subject_id: int, predicate: str, object_id: int) -> Optional[Claim]:
        return self.session.exec(
            select(Claim).where(
                Claim.subject_id == subject_id,
                Claim.predicate == predicate,
                Claim.object_id == object_id,
            )
        ).first()

    def find_claims_with_subject_predicate(self, subject_id: int, predicate: str) -> Sequence[Claim]:
        return self.session.exec(
            select(Claim).where(Claim.subject_id == subject_id, Claim.predicate == predicate)
        ).all()

    def frequent_predicate_pairs(self, min_count: int = 3) -> List[Tuple[str, str, int]]:
        """
        Find (predicate_1, predicate_2) pairs that co-occur via a shared
        intermediate entity: subject --p1--> mid --p2--> object.
        Used to surface candidates worth proposing an InferenceRule for.
        """
        c1 = Claim
        results = self.session.exec(
            select(Claim.predicate).distinct()
        ).all()
        # Build pair counts by joining Claim to itself on object_id == subject_id
        from sqlalchemy import alias
        c2 = alias(Claim.__table__, name="c2")
        stmt = (
            select(
                Claim.predicate,
                c2.c.predicate,
                func.count().label("cnt"),
            )
            .select_from(Claim.__table__.join(c2, Claim.__table__.c.object_id == c2.c.subject_id))
            .group_by(Claim.predicate, c2.c.predicate)
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

    def get_rule(self, rule_id: int) -> Optional[InferenceRule]:
        return self.session.get(InferenceRule, rule_id)

    def get_rules_by_status(self, status: str) -> Sequence[InferenceRule]:
        return self.session.exec(select(InferenceRule).where(InferenceRule.status == status)).all()

    def get_approved_rules(self) -> Sequence[InferenceRule]:
        return self.session.exec(
            select(InferenceRule).where(
                InferenceRule.human_approved == True,  # noqa: E712
                InferenceRule.rule_type == "compose",
            )
        ).all()

    def existing_rule_for_pair(self, predicate_1: str, predicate_2: str) -> Optional[InferenceRule]:
        return self.session.exec(
            select(InferenceRule).where(
                InferenceRule.predicate_1 == predicate_1,
                InferenceRule.predicate_2 == predicate_2,
            )
        ).first()

    # --- InferredClaim ---

    def create_inferred_claim(self, ic: InferredClaim) -> InferredClaim:
        self.session.add(ic)
        self.session.commit()
        self.session.refresh(ic)
        return ic

    def get_inferred_claim(self, subject_id: int, predicate: str, object_id: int) -> Optional[InferredClaim]:
        return self.session.exec(
            select(InferredClaim).where(
                InferredClaim.subject_id == subject_id,
                InferredClaim.predicate == predicate,
                InferredClaim.object_id == object_id,
            )
        ).first()

    def get_unreviewed_contradictions(self) -> Sequence[InferredClaim]:
        return self.session.exec(
            select(InferredClaim).where(
                InferredClaim.contradicts_claim_id.is_not(None),
                InferredClaim.reviewed == False,  # noqa: E712
            )
        ).all()
