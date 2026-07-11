import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.schema import (
    AgentRouteFallback,
    Artifact,
    ArtifactRelation,
    InferenceRule,
    ProviderConfig,
    Universe,
)
from app.services.inference_rule_service import InferenceRuleService


def _make_universe(db, name="TestUniverse"):
    u = Universe(name=name, is_explored=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_entity(db, universe_id, name, _entity_type="Thing"):
    e = Artifact(name=name, type="entity", universe_id=universe_id)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _make_claim(db, subject_id, predicate, object_id):
    subj = db.get(Artifact, subject_id)
    c = ArtifactRelation(
        universe_id=subj.universe_id, from_artifact_id=subject_id,
        to_artifact_id=object_id, relation_type=predicate
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _fake_llm_response(content: dict):
    """Mimics the (response, model_name, key_id) tuple call_llm returns."""
    msg = MagicMock()
    msg.content = json.dumps(content)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
class TestProposeAndCritique:
    async def test_approve_path_produces_critiqued_rule(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)

        proposer_reply = _fake_llm_response(
            {
                "predicate_1": "USES",
                "predicate_2": "GENERATES",
                "implied_predicate": "PRODUCES",
                "rule_type": "compose",
                "rationale": (
                    "USES then GENERATES composes to a direct production relationship."
                ),
            }
        )
        critic_blind_reply = _fake_llm_response(
            {
                "verdict": "APPROVE",
                "revised_implied_predicate": None,
                "revised_rule_type": None,
                "rationale": "Composition looks structurally sound.",
            }
        )
        critic_final_reply = _fake_llm_response(
            {
                "verdict": "APPROVE",
                "revised_implied_predicate": None,
                "revised_rule_type": None,
                "rationale": "Rationale confirms my independent judgment.",
            }
        )

        call_sequence = [
            (proposer_reply, "proposer-model", None),
            (critic_blind_reply, "critic-model", None),
            (critic_final_reply, "critic-model", None),
        ]

        with patch(
            "app.services.inference_rule_service.model_router.call_llm",
            new=AsyncMock(side_effect=call_sequence),
        ):
            svc = InferenceRuleService(session=ephemeral_db)
            rule = await svc.propose_and_critique(
                "USES", "GENERATES", run_id="test-run"
            )

        assert rule.status == "CRITIQUED"
        assert rule.implied_predicate == "PRODUCES"
        assert rule.proposer_model == "proposer-model"
        assert rule.critic_model == "critic-model"
        assert rule.critic_verdict == "APPROVE"
        assert rule.human_approved is False  # never auto-approved

    async def test_reject_path_marks_rule_rejected(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)

        proposer_reply = _fake_llm_response(
            {
                "predicate_1": "USES",
                "predicate_2": "GENERATES",
                "implied_predicate": "PRODUCES",
                "rule_type": "compose",
                "rationale": "Seems plausible.",
            }
        )
        critic_blind_reply = _fake_llm_response(
            {
                "verdict": "REJECT",
                "revised_implied_predicate": None,
                "revised_rule_type": None,
                "rationale": (
                    "Counterexample: USES does not always imply causal generation."
                ),
            }
        )
        critic_final_reply = _fake_llm_response(
            {
                "verdict": "REJECT",
                "revised_implied_predicate": None,
                "revised_rule_type": None,
                "rationale": "Rationale does not address the counterexample.",
            }
        )
        call_sequence = [
            (proposer_reply, "proposer-model", None),
            (critic_blind_reply, "critic-model", None),
            (critic_final_reply, "critic-model", None),
        ]

        with patch(
            "app.services.inference_rule_service.model_router.call_llm",
            new=AsyncMock(side_effect=call_sequence),
        ):
            svc = InferenceRuleService(session=ephemeral_db)
            rule = await svc.propose_and_critique(
                "USES", "GENERATES", run_id="test-run"
            )

        assert rule.status == "REJECTED"

    async def test_revise_path_applies_critic_correction(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)

        proposer_reply = _fake_llm_response(
            {
                "predicate_1": "USES",
                "predicate_2": "GENERATES",
                "implied_predicate": "MAKES",
                "rule_type": "compose",
                "rationale": "initial guess",
            }
        )
        critic_blind_reply = _fake_llm_response(
            {
                "verdict": "REVISE",
                "revised_implied_predicate": "PRODUCES",
                "revised_rule_type": "compose",
                "rationale": "MAKES is imprecise, PRODUCES is clearer.",
            }
        )
        critic_final_reply = _fake_llm_response(
            {
                "verdict": "REVISE",
                "revised_implied_predicate": "PRODUCES",
                "revised_rule_type": "compose",
                "rationale": "Sticking with my revision.",
            }
        )
        call_sequence = [
            (proposer_reply, "proposer-model", None),
            (critic_blind_reply, "critic-model", None),
            (critic_final_reply, "critic-model", None),
        ]

        with patch(
            "app.services.inference_rule_service.model_router.call_llm",
            new=AsyncMock(side_effect=call_sequence),
        ):
            svc = InferenceRuleService(session=ephemeral_db)
            rule = await svc.propose_and_critique(
                "USES", "GENERATES", run_id="test-run"
            )

        assert rule.status == "CRITIQUED"
        assert rule.implied_predicate == "PRODUCES"  # revised value applied

    async def test_critic_call_excludes_proposer_provider(self, ephemeral_db):
        """Independence guard: the critic's call_llm invocation must pass
        exclude_provider_id matching the proposer's resolved provider."""
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        _make_claim(ephemeral_db, a.id, "USES", b.id)
        _make_claim(ephemeral_db, b.id, "GENERATES", c.id)

        provider_a = ProviderConfig(name="provider-a", provider_type="custom")
        ephemeral_db.add(provider_a)
        ephemeral_db.commit()
        ephemeral_db.refresh(provider_a)

        route = AgentRouteFallback(
            task_type="Rule Proposer",
            priority=0,
            provider_id=provider_a.id,
            models="fake",
        )
        ephemeral_db.add(route)
        ephemeral_db.commit()

        proposer_reply = _fake_llm_response(
            {
                "predicate_1": "USES",
                "predicate_2": "GENERATES",
                "implied_predicate": "PRODUCES",
                "rule_type": "compose",
                "rationale": "ok",
            }
        )
        critic_reply = _fake_llm_response(
            {
                "verdict": "APPROVE",
                "revised_implied_predicate": None,
                "revised_rule_type": None,
                "rationale": "ok",
            }
        )

        mock_call_llm = AsyncMock(
            side_effect=[
                (proposer_reply, "proposer-model", None),
                (critic_reply, "critic-model", None),
                (critic_reply, "critic-model", None),
            ]
        )
        with patch(
            "app.services.inference_rule_service.model_router.call_llm",
            new=mock_call_llm,
        ):
            svc = InferenceRuleService(session=ephemeral_db)
            await svc.propose_and_critique("USES", "GENERATES", run_id="test-run")


        # First call = proposer (no exclude), second+third = critic calls
        critic_calls = mock_call_llm.await_args_list[1:]
        for call in critic_calls:
            assert call.kwargs.get("exclude_provider_id") == provider_a.id


class TestCandidateDiscovery:
    def test_find_candidate_pairs_excludes_existing_rules(self, ephemeral_db):
        u = _make_universe(ephemeral_db)
        a = _make_entity(ephemeral_db, u.id, "A")
        b = _make_entity(ephemeral_db, u.id, "B")
        c = _make_entity(ephemeral_db, u.id, "C")
        d = _make_entity(ephemeral_db, u.id, "D")
        e = _make_entity(ephemeral_db, u.id, "E")
        f = _make_entity(ephemeral_db, u.id, "F")
        for s, p, o in [
            (a.id, "USES", b.id),
            (b.id, "GENERATES", c.id),
            (c.id, "USES", d.id),
            (d.id, "GENERATES", e.id),
            (e.id, "USES", f.id),
            (f.id, "GENERATES", a.id),
        ]:
            _make_claim(ephemeral_db, s, p, o)

        existing_rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="APPROVED",
            human_approved=True,
        )
        ephemeral_db.add(existing_rule)
        ephemeral_db.commit()

        svc = InferenceRuleService()
        candidates = svc.find_candidate_pairs()
        pair_tuples = [(p1, p2) for (p1, p2, cnt) in candidates]
        assert ("USES", "GENERATES") not in pair_tuples  # already has a rule


class TestRuleApprovalLifecycle:
    def test_approve_and_reject(self, ephemeral_db):
        rule = InferenceRule(
            predicate_1="USES",
            predicate_2="GENERATES",
            implied_predicate="PRODUCES",
            status="CRITIQUED",
        )
        ephemeral_db.add(rule)
        ephemeral_db.commit()
        ephemeral_db.refresh(rule)

        svc = InferenceRuleService()
        approved = svc.approve_rule(rule.id)
        assert approved.human_approved is True
        assert approved.status == "APPROVED"

        rejected = svc.reject_rule(rule.id)
        assert rejected.human_approved is False
        assert rejected.status == "REJECTED"

    def test_approve_nonexistent_rule_returns_none(self, _ephemeral_db):
        svc = InferenceRuleService()
        assert svc.approve_rule(99999) is None
