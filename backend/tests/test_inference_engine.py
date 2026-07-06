import json
import pytest
from sqlmodel import Session, select
from app.db.schema import Universe, Entity, Claim, InferenceRule, InferredClaim, Setting
from app.repositories.inference import InferenceRepository
from app.services.inference_engine_service import InferenceEngineService


def _make_universe(db, name="TestUniverse"):
    u = Universe(name=name, is_explored=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_entity(db, universe_id, name, entity_type="Thing"):
    e = Entity(name=name, entity_type=entity_type, universe_id=universe_id)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _make_claim(db, subject_id, predicate, object_id, **kwargs):
    from app.db.schema import Predicate
    pred_obj = db.exec(select(Predicate).where(Predicate.canonical_name == predicate)).first()
    if not pred_obj:
        pred_obj = Predicate(canonical_name=predicate)
        db.add(pred_obj)
        db.flush()
    c = Claim(subject_id=subject_id, predicate_id=pred_obj.id, predicate=predicate, object_entity_id=object_id, **kwargs)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_rule(db, p1, p2, implied, approved=True):
    r = InferenceRule(
        predicate_1=p1, predicate_2=p2, implied_predicate=implied,
        status="APPROVED" if approved else "PROPOSED", human_approved=approved,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


class TestInferenceRepository:
    def test_frequent_predicate_pairs_detects_chain(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        d = _make_entity(ephemeral_db, u.id, "D")
        e = _make_entity(ephemeral_db, u.id, "E")
        f = _make_entity(ephemeral_db, u.id, "F")
        # 3 occurrences of USES -> GENERATES chain
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        _make_claim(ephemeral_db, c.id, "USES", d.id)
        _make_claim(ephemeral_db, d.id, "GENERATES", e.id)
        _make_claim(ephemeral_db, e.id, "USES", f.id)
        _make_claim(ephemeral_db, f.id, "GENERATES", a.id)

        repo = InferenceRepository(ephemeral_db)
        pairs = repo.frequent_predicate_pairs(min_count=3)
        pair_tuples = [(p1, p2) for (p1, p2, cnt) in pairs]
        assert ("USES", "GENERATES") in pair_tuples

    def test_frequent_predicate_pairs_below_threshold_excluded(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        # Only 1 occurrence -- below default min_count of 3
        _make_claim(ephemeral_db, a.id, "RARE_PRED", b.id)
        _make_claim(ephemeral_db, b.id, "OTHER_PRED", c.id)

        repo = InferenceRepository(ephemeral_db)
        pairs = repo.frequent_predicate_pairs(min_count=3)
        pair_tuples = [(p1, p2) for (p1, p2, cnt) in pairs]
        assert ("RARE_PRED", "OTHER_PRED") not in pair_tuples

    def test_existing_rule_for_pair(self, ephemeral_db):
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")
        repo = InferenceRepository(ephemeral_db)
        assert repo.existing_rule_for_pair("USES", "GENERATES") is not None
        assert repo.existing_rule_for_pair("FOO", "BAR") is None

    def test_frequent_predicate_pairs_handles_self_loop_chain(self, ephemeral_db):
        """A cycle (F -> A via GENERATES, closing the loop back to the start)
        must not crash the self-join query or double count incorrectly."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        # Self-referential: A USES A (degenerate but should not crash)
        _make_claim(ephemeral_db, a.id, "USES", a.id)
        _make_claim(ephemeral_db, a.id, "GENERATES", b.id)

        repo = InferenceRepository(ephemeral_db)
        # Should not raise, even with a self-loop in the graph.
        pairs = repo.frequent_predicate_pairs(min_count=1)
        pair_tuples = [(p1, p2) for (p1, p2, cnt) in pairs]
        assert ("USES", "GENERATES") in pair_tuples

    def test_get_approved_rules_excludes_unapproved(self, ephemeral_db):
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES", approved=True)
        _make_rule(ephemeral_db, "FOO", "BAR", "BAZ", approved=False)
        repo = InferenceRepository(ephemeral_db)
        approved = repo.get_approved_rules()
        assert len(approved) == 1
        assert approved[0].predicate_1 == "USES"

    def test_get_approved_rules_excludes_block_type(self, ephemeral_db):
        approved_compose = InferenceRule(predicate_1="USES", predicate_2="GENERATES", implied_predicate="PRODUCES",
                                          rule_type="compose", status="APPROVED", human_approved=True)
        approved_block = InferenceRule(predicate_1="FOO", predicate_2="BAR", implied_predicate="BAZ",
                                        rule_type="block", status="APPROVED", human_approved=True)
        ephemeral_db.add_all([approved_compose, approved_block])
        ephemeral_db.commit()
        repo = InferenceRepository(ephemeral_db)
        approved = repo.get_approved_rules()
        assert len(approved) == 1
        assert approved[0].rule_type == "compose"


class TestInferenceEngineDepth:
    def test_depth_2_composition(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        c1 = _make_claim(ephemeral_db, a.id, "USES", b.id)
        c2 = _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")

        svc = InferenceEngineService()
        svc.set_max_depth(2)
        created = svc.materialize_inferred_claims()

        assert len(created) == 1
        ic = created[0]
        assert ic.subject_id == a.id
        assert ic.predicate == "PRODUCES"
        assert ic.object_id == c.id
        assert json.loads(ic.path_claim_ids) == [c1.id, c2.id]

    def test_depth_3_composition_requires_second_rule(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        d = _make_entity(ephemeral_db, u.id, "D")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        _make_claim(ephemeral_db, c.id, "MITIGATED_BY", d.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")
        _make_rule(ephemeral_db, "PRODUCES", "MITIGATED_BY", "REQUIRES_MITIGATION_VIA")

        svc = InferenceEngineService()
        svc.set_max_depth(3)
        created = svc.materialize_inferred_claims()

        predicates = {(ic.subject_id, ic.predicate, ic.object_id) for ic in created}
        assert (a.id, "PRODUCES", c.id) in predicates
        assert (a.id, "REQUIRES_MITIGATION_VIA", d.id) in predicates

    def test_depth_limit_prevents_third_hop(self, ephemeral_db):
        """With max_composition_depth=2, a 3-hop chain must NOT be composed,
        even though the rules exist to do it."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        d = _make_entity(ephemeral_db, u.id, "D")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        _make_claim(ephemeral_db, c.id, "MITIGATED_BY", d.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")
        _make_rule(ephemeral_db, "PRODUCES", "MITIGATED_BY", "REQUIRES_MITIGATION_VIA")

        svc = InferenceEngineService()
        svc.set_max_depth(2)
        created = svc.materialize_inferred_claims()

        predicates = {(ic.subject_id, ic.predicate, ic.object_id) for ic in created}
        assert (a.id, "PRODUCES", c.id) in predicates
        assert (a.id, "REQUIRES_MITIGATION_VIA", d.id) not in predicates

    def test_rerun_does_not_duplicate(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")

        svc = InferenceEngineService()
        first = svc.materialize_inferred_claims()
        second = svc.materialize_inferred_claims()

        assert len(first) == 1
        assert len(second) == 0  # already materialized, no duplicate

    def test_depth_setting_persists_and_validates(self, ephemeral_db):
        svc = InferenceEngineService()
        assert svc.get_max_depth() == 2  # default
        svc.set_max_depth(5)
        assert svc.get_max_depth() == 5
        with pytest.raises(ValueError):
            svc.set_max_depth(0)

    def test_depth_1_produces_no_inferences(self, ephemeral_db):
        """depth=1 means 'no composition at all' -- a single asserted claim
        isn't an inference. Even with a perfectly valid rule and matching
        claims present, nothing should be materialized."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")

        svc = InferenceEngineService()
        svc.set_max_depth(1)
        created = svc.materialize_inferred_claims()
        assert created == []

    def test_block_rule_type_excluded_from_materialization(self, ephemeral_db):
        """A rule explicitly marked rule_type='block' represents a
        composition the proposer/critic considered and rejected as
        generally invalid -- it must never be used to materialize
        inferences, even if human_approved happens to be True."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        r = InferenceRule(predicate_1="USES", predicate_2="GENERATES", implied_predicate="PRODUCES",
                           rule_type="block", status="APPROVED", human_approved=True)
        ephemeral_db.add(r)
        ephemeral_db.commit()

        svc = InferenceEngineService()
        created = svc.materialize_inferred_claims()
        assert created == []

    def test_unapproved_rule_not_used_even_if_critiqued_approve(self, ephemeral_db):
        """A rule the critic marked APPROVE but that a human hasn't yet
        flipped human_approved=True on must not be used -- two-model
        agreement is never sufficient on its own."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        r = InferenceRule(predicate_1="USES", predicate_2="GENERATES", implied_predicate="PRODUCES",
                           rule_type="compose", status="CRITIQUED", critic_verdict="APPROVE",
                           human_approved=False)
        ephemeral_db.add(r)
        ephemeral_db.commit()

        svc = InferenceEngineService()
        created = svc.materialize_inferred_claims()
        assert created == []

    def test_depth_4_chain_with_three_rules(self, ephemeral_db):
        """Extends the depth-3 case one hop further to confirm the
        incremental-frontier composition loop generalizes past a single
        extra hop, not just exactly 3."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        d = _make_entity(ephemeral_db, u.id, "D")
        e = _make_entity(ephemeral_db, u.id, "E")
        _make_claim(ephemeral_db, a.id, "P1", b.id)
        _make_claim(ephemeral_db, b.id, "P2", c.id)
        _make_claim(ephemeral_db, c.id, "P3", d.id)
        _make_claim(ephemeral_db, d.id, "P4", e.id)
        _make_rule(ephemeral_db, "P1", "P2", "Q1")
        _make_rule(ephemeral_db, "Q1", "P3", "Q2")
        _make_rule(ephemeral_db, "Q2", "P4", "Q3")

        svc = InferenceEngineService()
        svc.set_max_depth(4)
        created = svc.materialize_inferred_claims()

        results = {(ic.subject_id, ic.predicate, ic.object_id) for ic in created}
        assert (a.id, "Q1", c.id) in results
        assert (a.id, "Q2", d.id) in results
        assert (a.id, "Q3", e.id) in results

    def test_depth_3_setting_caps_before_4th_hop(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        d = _make_entity(ephemeral_db, u.id, "D")
        e = _make_entity(ephemeral_db, u.id, "E")
        _make_claim(ephemeral_db, a.id, "P1", b.id)
        _make_claim(ephemeral_db, b.id, "P2", c.id)
        _make_claim(ephemeral_db, c.id, "P3", d.id)
        _make_claim(ephemeral_db, d.id, "P4", e.id)
        _make_rule(ephemeral_db, "P1", "P2", "Q1")
        _make_rule(ephemeral_db, "Q1", "P3", "Q2")
        _make_rule(ephemeral_db, "Q2", "P4", "Q3")

        svc = InferenceEngineService()
        svc.set_max_depth(3)
        created = svc.materialize_inferred_claims()

        results = {(ic.subject_id, ic.predicate, ic.object_id) for ic in created}
        assert (a.id, "Q2", d.id) in results  # depth 3, allowed
        assert (a.id, "Q3", e.id) not in results  # depth 4, blocked by cap


class TestContradictionDetection:
    def test_contradiction_flagged_not_resolved(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        conflicting = _make_entity(ephemeral_db, u.id, "Conflicting")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        # Directly asserted, conflicting claim: A PRODUCES something else
        conflict_claim = _make_claim(ephemeral_db, a.id, "PRODUCES", conflicting.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")

        svc = InferenceEngineService()
        created = svc.materialize_inferred_claims()

        assert len(created) == 1
        ic = created[0]
        assert ic.contradicts_claim_id == conflict_claim.id
        assert ic.reviewed is False

        unreviewed = svc.get_unreviewed_contradictions()
        assert len(unreviewed) == 1
        assert unreviewed[0].id == ic.id

    def test_no_contradiction_when_objects_agree(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)
        # Asserted claim agrees with what will be inferred
        _make_claim(ephemeral_db, a.id, "PRODUCES", c.id)
        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")

        svc = InferenceEngineService()
        created = svc.materialize_inferred_claims()

        assert len(created) == 1
        assert created[0].contradicts_claim_id is None


class TestCrossUniverseGenericity:
    def test_same_rule_applies_across_unrelated_universes(self, ephemeral_db):
        """The engine has no concept of 'setting' -- a rule fires wherever
        its predicates match, regardless of which fictional universe the
        entities belong to."""
        battletech = _make_universe(ephemeral_db, "Battletech")
        halo = _make_universe(ephemeral_db, "Halo")
        lotr = _make_universe(ephemeral_db, "LOTR")

        mech = _make_entity(ephemeral_db, battletech.id, "BattleMech")
        engine_e = _make_entity(ephemeral_db, battletech.id, "Fusion Engine")
        heat = _make_entity(ephemeral_db, battletech.id, "Heat")

        spartan = _make_entity(ephemeral_db, halo.id, "Master Chief")
        mjolnir = _make_entity(ephemeral_db, halo.id, "MJOLNIR Armor")
        shields = _make_entity(ephemeral_db, halo.id, "Energy Shields")

        ring = _make_entity(ephemeral_db, lotr.id, "The One Ring")
        will = _make_entity(ephemeral_db, lotr.id, "Sauron's Will")
        corruption = _make_entity(ephemeral_db, lotr.id, "Corruption")

        _make_claim(ephemeral_db, mech.id, "USES", engine_e.id)
        _make_claim(ephemeral_db, engine_e.id, "GENERATES", heat.id)
        _make_claim(ephemeral_db, spartan.id, "USES", mjolnir.id)
        _make_claim(ephemeral_db, mjolnir.id, "GENERATES", shields.id)
        # LOTR uses an entirely different predicate vocabulary
        _make_claim(ephemeral_db, ring.id, "EMBODIES", will.id)
        _make_claim(ephemeral_db, will.id, "CAUSES", corruption.id)

        _make_rule(ephemeral_db, "USES", "GENERATES", "PRODUCES")

        svc = InferenceEngineService()
        created = svc.materialize_inferred_claims()

        results = {(ic.subject_id, ic.predicate, ic.object_id) for ic in created}
        assert (mech.id, "PRODUCES", heat.id) in results
        assert (spartan.id, "PRODUCES", shields.id) in results
        assert len(created) == 2  # nothing derived for LOTR's unrelated predicates
