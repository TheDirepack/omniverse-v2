from collections.abc import Sequence
from typing import Any

from sqlmodel import Session, func, select

from app.db.schema import ArtifactRelation, InferenceRule, InferredClaim


class InferenceRepository:
    """Stateless repository: takes a live session per call, matching the
    fix in 5f45596 (services own session lifecycle, repos never hold one)."""

    def __init__(self, session: Session):
        self.session = session

    # --- Artifact Relation graph ---

    def get_claims_by_predicate(
        self,
        predicate: str,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(ArtifactRelation).where(
            ArtifactRelation.relation_type == predicate
        )
        if fields:
            proj_fields = [
                getattr(ArtifactRelation, f)
                for f in fields
                if hasattr(ArtifactRelation, f)
            ]
            if proj_fields:
                stmt = select(*proj_fields).where(
                    ArtifactRelation.relation_type == predicate
                )
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def get_claims_for_subject(
        self,
        subject_id: int,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(ArtifactRelation).where(
            ArtifactRelation.from_artifact_id == subject_id
        )
        if fields:
            proj_fields = [
                getattr(ArtifactRelation, f)
                for f in fields
                if hasattr(ArtifactRelation, f)
            ]
            if proj_fields:
                stmt = select(*proj_fields).where(
                    ArtifactRelation.from_artifact_id == subject_id
                )
        return self.session.exec(stmt.offset(offset).limit(limit)).all()

    def find_claim(
        self, subject_id: int, predicate: str, object_id: int
    ) -> ArtifactRelation | None:
        stmt = select(ArtifactRelation).where(
            ArtifactRelation.from_artifact_id == subject_id,
            ArtifactRelation.relation_type == predicate,
            ArtifactRelation.to_artifact_id == object_id,
        )
        return self.session.exec(stmt).first()

    def find_claims_with_subject_predicate(
        self,
        subject_id: int,
        predicate: str,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
    ) -> Sequence[Any]:
        stmt = select(ArtifactRelation).where(
            ArtifactRelation.from_artifact_id == subject_id,
            ArtifactRelation.relation_type == predicate,
        )
        if fields:
            proj_fields = [
                getattr(ArtifactRelation, f)
                for f in fields
                if hasattr(ArtifactRelation, f)
            ]
            if proj_fields:
                stmt = (
                    select(*proj_fields)
                    .where(
                        ArtifactRelation.from_artifact_id == subject_id,
                        ArtifactRelation.relation_type == predicate,
                    )
                )

        res = self.session.exec(stmt.offset(offset).limit(limit)).all()
        if res:
            return res

        return []

    def frequent_predicate_pairs(
        self, min_count: int = 3
    ) -> list[tuple[str, str, int]]:
        """
        Find (predicate_1, predicate_2) pairs that co-occur via a shared
        intermediate entity: subject --p1--> mid --p2--> object.
        Used to surface candidates worth proposing an InferenceRule for.
        """
        from sqlalchemy import alias

        rel1 = ArtifactRelation.__table__
        rel2 = alias(ArtifactRelation.__table__, name="rel2")

        stmt = (
            select(
                rel1.c.relation_type,
                rel2.c.relation_type,
                func.count(),
            )
            .select_from(
                rel1.join(
                    rel2, rel1.c.to_artifact_id == rel2.c.from_artifact_id
                )
            )
            .group_by(
                rel1.c.relation_type,
                rel2.c.relation_type,
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
