"""
Full-cycle integration tests against a real llama-server process.

These make real HTTP calls through litellm to an actual local model (no
call_llm mocking), exercising: real prompt formatting, real JSON parsing of
a real (imperfect) model's output, the real independence guard at the
routing layer, and the full propose -> critique -> approve -> materialize
pipeline end to end.

Marked `slow` and `network` (declared in pytest.ini) since they spawn a
subprocess and depend on model inference latency -- excluded from the
default `-m "not slow"` CI run, opt-in via `pytest -m slow`.

Skips gracefully (see tests/conftest.py::llama_server) if llama-server or
the real model weights aren't available in the current environment.
"""
import json
import pytest
from app.db.schema import Universe, Entity, Claim, InferenceRule, ProviderConfig, AgentRouteFallback
from app.services.inference_rule_service import InferenceRuleService
from app.services.inference_engine_service import InferenceEngineService


def _register_provider(db, base_url: str, name: str, model: str = "qwen3-0.6b"):
    provider = ProviderConfig(
        name=name,
        provider_type="custom",
        base_url=base_url,
        models=model,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


def _register_route(db, task_type: str, provider_id: int, models: str = "qwen3-0.6b", priority: int = 0):
    route = AgentRouteFallback(task_type=task_type, provider_id=provider_id, models=models, priority=priority)
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
class TestFullCycleAgainstRealModel:
    async def test_propose_and_critique_real_model(self, ephemeral_db, llama_server):
        """
        Real proposer + real critic calls against the actual model. Since a
        small quantized model's exact wording/JSON validity isn't
        guaranteed, this asserts STRUCTURE (rule created, both models
        recorded, rationale present, status is one of the valid terminal
        states) rather than exact predicate text.
        """
        u = Universe(name="TEST_FullCycle", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        ephemeral_db.refresh(u)

        a = Entity(name="BattleMech", entity_type="Unit", universe_id=u.id)
        b = Entity(name="Fusion Engine", entity_type="Component", universe_id=u.id)
        c = Entity(name="Heat", entity_type="Concept", universe_id=u.id)
        ephemeral_db.add_all([a, b, c])
        ephemeral_db.commit()
        for e in [a, b, c]:
            ephemeral_db.refresh(e)

        ephemeral_db.add_all([
            Claim(subject_id=a.id, predicate="USES", object_id=b.id),
            Claim(subject_id=b.id, predicate="GENERATES", object_id=c.id),
        ])
        ephemeral_db.commit()

        # Single real server backs two distinct ProviderConfig rows so the
        # independence guard has a genuine "alternative provider" to pick,
        # even though physically the same process answers both -- the guard
        # operates on provider_id, not on which process is behind it.
        provider_a = _register_provider(ephemeral_db, f"{llama_server}/v1", "llama-proposer")
        provider_b = _register_provider(ephemeral_db, f"{llama_server}/v1", "llama-critic")
        _register_route(ephemeral_db, "Rule Proposer", provider_a.id)
        _register_route(ephemeral_db, "Rule Critic", provider_b.id)

        svc = InferenceRuleService()
        rule = await svc.propose_and_critique("USES", "GENERATES", run_id="full-cycle-test")

        assert rule.id is not None
        assert rule.predicate_1 == "USES"
        assert rule.predicate_2 == "GENERATES"
        assert rule.status in {"CRITIQUED", "REJECTED"}
        assert rule.proposer_model is not None
        assert rule.critic_model is not None
        assert rule.proposer_rationale  # non-empty
        assert rule.critic_rationale  # non-empty
        assert rule.human_approved is False  # never auto-approved, regardless of model output
        # implied_predicate may be empty string if the small model produced
        # malformed JSON that _safe_json partially recovered -- log it for
        # visibility rather than asserting an exact value.
        print(f"\n[full-cycle] proposer={rule.proposer_model} critic={rule.critic_model} "
              f"implied_predicate={rule.implied_predicate!r} verdict={rule.critic_verdict!r} status={rule.status}")

    async def test_full_pipeline_propose_approve_materialize(self, ephemeral_db, llama_server):
        """
        End-to-end: real propose+critique, then human approval (never
        automatic), then real path materialization using whatever
        implied_predicate the real model actually proposed.
        """
        u = Universe(name="TEST_FullPipeline", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        ephemeral_db.refresh(u)

        a = Entity(name="Reactor", entity_type="Component", universe_id=u.id)
        b = Entity(name="Coolant System", entity_type="Component", universe_id=u.id)
        c = Entity(name="Waste Heat", entity_type="Concept", universe_id=u.id)
        ephemeral_db.add_all([a, b, c])
        ephemeral_db.commit()
        for e in [a, b, c]:
            ephemeral_db.refresh(e)

        ephemeral_db.add_all([
            Claim(subject_id=a.id, predicate="POWERS", object_id=b.id),
            Claim(subject_id=b.id, predicate="EMITS", object_id=c.id),
        ])
        ephemeral_db.commit()

        provider = _register_provider(ephemeral_db, f"{llama_server}/v1", "llama-single")
        _register_route(ephemeral_db, "Rule Proposer", provider.id)
        _register_route(ephemeral_db, "Rule Critic", provider.id)  # only one provider configured on purpose:
        # exercises the "independence guard could not be honored, logs a
        # warning and proceeds anyway" path for real, rather than mocking it.

        rule_svc = InferenceRuleService()
        rule = await rule_svc.propose_and_critique("POWERS", "EMITS", run_id="full-pipeline-test")

        if rule.status == "REJECTED":
            pytest.skip(
                f"Real model rejected this composition (critic_rationale={rule.critic_rationale!r}); "
                "nothing to materialize. This is a valid model output, not a test failure -- "
                "rerun or adjust the example pair if this is consistently rejected."
            )

        # Human approval step -- required regardless of critic verdict.
        approved = rule_svc.approve_rule(rule.id)
        assert approved.human_approved is True
        assert approved.status == "APPROVED"

        if not approved.implied_predicate:
            pytest.skip("Real model produced an empty implied_predicate (malformed JSON); nothing to materialize.")

        engine_svc = InferenceEngineService()
        created = engine_svc.materialize_inferred_claims()

        matching = [ic for ic in created if ic.subject_id == a.id and ic.object_id == c.id]
        assert len(matching) == 1, (
            f"Expected exactly one InferredClaim from Reactor to Waste Heat via rule "
            f"'{approved.implied_predicate}', got: {[(ic.subject_id, ic.predicate, ic.object_id) for ic in created]}"
        )
        ic = matching[0]
        assert ic.predicate == approved.implied_predicate
        assert json.loads(ic.path_claim_ids)  # non-empty path, traceable to source claims
        print(f"\n[full-pipeline] materialized: Reactor --{ic.predicate}--> Waste Heat "
              f"(rule implied_predicate={approved.implied_predicate!r})")

    async def test_candidate_discovery_against_real_data(self, ephemeral_db, llama_server):
        """Confirms the frequent-pair scan + full pass work end to end
        without any mocking, using run_rule_proposal_pass (the actual
        manual-trigger entrypoint), not propose_and_critique directly."""
        u = Universe(name="TEST_Discovery", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        ephemeral_db.refresh(u)

        entities = [Entity(name=f"E{i}", entity_type="X", universe_id=u.id) for i in range(6)]
        ephemeral_db.add_all(entities)
        ephemeral_db.commit()
        for e in entities:
            ephemeral_db.refresh(e)

        # 3 occurrences of USES -> GENERATES, above the min_count threshold
        pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]
        claims = []
        for i, (s, o) in enumerate(pairs):
            predicate = "USES" if i % 2 == 0 else "GENERATES"
            claims.append(Claim(subject_id=entities[s].id, predicate=predicate, object_id=entities[o].id))
        ephemeral_db.add_all(claims)
        ephemeral_db.commit()

        provider = _register_provider(ephemeral_db, f"{llama_server}/v1", "llama-discovery")
        _register_route(ephemeral_db, "Rule Proposer", provider.id)
        _register_route(ephemeral_db, "Rule Critic", provider.id)

        svc = InferenceRuleService()
        results = await svc.run_rule_proposal_pass(run_id="discovery-test")

        assert len(results) >= 1
        for rule in results:
            assert rule.status in {"CRITIQUED", "REJECTED"}
            assert rule.human_approved is False
