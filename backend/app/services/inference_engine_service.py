from collections.abc import Sequence

from sqlmodel import Session

from app.db.schema import ArtifactRelation, InferredClaim
from app.db.session import engine
from app.repositories.inference import InferenceRepository
from app.repositories.settings import SettingsRepository

DEFAULT_MAX_DEPTH = 2


class InferenceEngineService:
    # Nothing in this class is aware of any specific fictional universe.
    # It operates purely on Entity ids and Claim.predicate strings — a
    # BattleTech rule (USES/GENERATES) and a Halo rule (WIELDS/POWERED_BY)
    # are handled identically, each scoped to whichever Entity rows their
    # predicates actually connect. Universe-specific meaning lives only in
    # the data (Entity.name, Entity.universe_id), never in this code.

    def __init__(self, session: Session | None = None):
        # Per 5f45596: no eager session at construction time.
        self.session = session

    def get_max_depth(self) -> int:
        session = self.session or Session(engine)
        try:
            setting = SettingsRepository(session).get_setting("max_composition_depth")
            if setting and setting.value:
                try:
                    return int(setting.value)
                except ValueError:
                    return DEFAULT_MAX_DEPTH
            return DEFAULT_MAX_DEPTH
        finally:
            if not self.session:
                session.close()

    def set_max_depth(self, depth: int) -> None:
        if depth < 1:
            raise ValueError(
                "max_composition_depth must be at least 1"
            )
        session = self.session or Session(engine)
        try:
            SettingsRepository(session).upsert_setting(
                "max_composition_depth", str(depth)
            )
            session.commit()
        finally:
            if not self.session:
                session.close()

    def materialize_inferred_claims(self) -> list[InferredClaim]:
        """
        Manual-trigger pass: for each APPROVED+human_approved compose rule,
        walk 2-hop chains (subject -p1-> mid -p2-> object) and materialize the
        implied edge, up to the configured depth. Depth > 2 composes
        previously-materialized InferredClaims as an intermediate hop, capped
        at get_max_depth() to bound combinatorial growth in dense graphs.
        Rules and claims are read purely by predicate string, so this applies
        identically regardless of which universe(s) produced them.
        """
        max_depth = self.get_max_depth()
        if max_depth < 2:
            return []

        session = self.session or Session(engine)
        try:
            repo = InferenceRepository(session)
            approved_rules = list(repo.get_approved_rules())
            created: list[InferredClaim] = []

            # Depth 2: direct composition over asserted ArtifactRelations.
            for rule in approved_rules:
                first_hop = repo.get_claims_by_predicate(rule.predicate_1)
                for c1 in first_hop:
                    mid_id = c1.to_artifact_id
                    second_hops = repo.find_claims_with_subject_predicate(
                        mid_id, rule.predicate_2
                    )
                    for c2 in second_hops:
                        ic = self._materialize_edge(
                            repo, rule.id, rule.implied_predicate, c1, c2
                        )
                        if ic:
                            created.append(ic)

            # Depth > 2: compose an InferredClaim (as the "first hop") with a
            # further asserted ArtifactRelation, one additional hop per iteration,
            # bounded by max_depth.
            current_depth = 2
            frontier = created
            while current_depth < max_depth and frontier:
                next_frontier = []
                for rule in approved_rules:
                    for ic in frontier:
                        if ic.predicate != rule.predicate_1:
                            continue
                        second_hops = repo.find_claims_with_subject_predicate(
                            ic.object_id, rule.predicate_2
                        )
                        for c2 in second_hops:
                            new_ic = self._materialize_edge_from_inferred(
                                repo, rule.id, rule.implied_predicate, ic, c2
                            )
                            if new_ic:
                                next_frontier.append(new_ic)
                created.extend(next_frontier)
                frontier = next_frontier
                current_depth += 1

            for ic in created:
                session.refresh(ic)

            session.commit()
            return created
        finally:
            if not self.session:
                session.close()

    def _materialize_edge(
        self,
        repo: InferenceRepository,
        rule_id: int,
        implied_predicate: str,
        c1: ArtifactRelation,
        c2: ArtifactRelation,
    ) -> InferredClaim | None:
        obj_id = c2.to_artifact_id
        assert obj_id is not None
        existing = repo.get_inferred_claim(
            c1.from_artifact_id, implied_predicate, obj_id
        )
        if existing:
            return None
        contradicts_id = self._find_contradiction(
            repo, c1.from_artifact_id, implied_predicate, obj_id
        )
        ic = InferredClaim(
            subject_id=c1.from_artifact_id,
            predicate=implied_predicate,
            object_id=obj_id,
            derived_from_rule_id=rule_id,
            contradicts_claim_id=contradicts_id,
        )
        res = repo.create_inferred_claim(ic)
        repo.session.flush()
        repo.add_inferred_claim_paths(res.id, [c1.id, c2.id])
        return res

    def _materialize_edge_from_inferred(
        self,
        repo: InferenceRepository,
        rule_id: int,
        implied_predicate: str,
        ic_prev: InferredClaim,
        c2: ArtifactRelation,
    ) -> InferredClaim | None:
        obj_id = c2.to_artifact_id
        assert obj_id is not None
        existing = repo.get_inferred_claim(
            ic_prev.subject_id, implied_predicate, obj_id
        )
        if existing:
            return None
        contradicts_id = self._find_contradiction(
            repo, ic_prev.subject_id, implied_predicate, obj_id
        )
        prev_path = repo.get_inferred_claim_paths(ic_prev.id)
        ic = InferredClaim(
            subject_id=ic_prev.subject_id,
            predicate=implied_predicate,
            object_id=obj_id,
            derived_from_rule_id=rule_id,
            contradicts_claim_id=contradicts_id,
        )
        res = repo.create_inferred_claim(ic)
        session = repo.session
        session.flush()
        repo.add_inferred_claim_paths(res.id, [*prev_path, c2.id])
        return res

    def _find_contradiction(
        self,
        repo: InferenceRepository,
        subject_id: int,
        predicate: str,
        object_id: int,
    ) -> int | None:
        existing_relations = repo.find_claims_with_subject_predicate(
            subject_id, predicate
        )
        for existing in existing_relations:
            existing_obj_id = existing.to_artifact_id
            if existing_obj_id != object_id:
                return existing.id
        return None


    def get_unreviewed_contradictions(self) -> Sequence[InferredClaim]:
        session = self.session or Session(engine)
        try:
            return InferenceRepository(session).get_unreviewed_contradictions()
        finally:
            if not self.session:
                session.close()
