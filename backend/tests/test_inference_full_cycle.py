"""
Full-cycle integration tests against Groq API.

Makes real HTTP calls through litellm to Groq (no call_llm mocking),
exercising: real prompt formatting, real JSON parsing of a real model's
output, the real independence guard at the routing layer, and the full
propose -> critique -> approve -> materialize pipeline end to end.

Marked `slow` and `network` since they depend on external API latency
-- excluded from the default `-m "not slow"` CI run, opt-in via
`pytest -m "slow"` (or ./test.sh --slow).

Skips gracefully if the Groq API key is not configured in
tests/provider_config.py.
"""

import asyncio
import json
import logging

import pytest

logger = logging.getLogger(__name__)
from app.db.schema import (
    AgentRouteFallback,
    Claim,
    Entity,
    ProviderConfig,
    ProviderKey,
    Universe,
)
from app.db.settings_session import settings_engine
from app.repositories.inference import InferenceRepository
from app.services.inference_engine_service import InferenceEngineService
from app.services.inference_rule_service import InferenceRuleService
from sqlmodel import Session

try:
    from tests.provider_config import PROVIDER_CREDENTIALS
except ImportError:
    PROVIDER_CREDENTIALS = {}

GROQ_CFG = PROVIDER_CREDENTIALS.get("groq", {})
GROQ_API_KEY = (GROQ_CFG.get("api_key") or "").strip()
GROQ_MODEL = GROQ_CFG.get("model") or "llama3-70b-8192"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

requires_groq = pytest.mark.skipif(
    not GROQ_API_KEY,
    reason="Groq API key not configured in tests/provider_config.py",
)


def _register_groq_provider(
    session: Session, name: str, models: str | None = None
) -> ProviderConfig:
    p = ProviderConfig(
        name=name,
        provider_type="groq",
        base_url=GROQ_BASE_URL,
        models=models or GROQ_MODEL,
    )
    session.add(p)
    session.flush()
    session.add(ProviderKey(provider_id=p.id, api_key=GROQ_API_KEY, priority=0))
    session.commit()
    session.refresh(p)
    return p


def _register_route(
    session: Session,
    task_type: str,
    provider_id: int,
    models: str | None = None,
    priority: int = 0,
):
    route = AgentRouteFallback(
        task_type=task_type,
        provider_id=provider_id,
        models=models or GROQ_MODEL,
        priority=priority,
    )
    session.add(route)
    session.commit()
    session.refresh(route)
    return route


@pytest.mark.slow
@pytest.mark.network
@pytest.mark.asyncio
@requires_groq
class TestFullCycleAgainstGroq:
    @pytest.fixture(autouse=True)
    async def _throttle(self):
        await asyncio.sleep(8)
        yield

    async def test_propose_and_critique_real_model(self, ephemeral_db):
        logger.info(
            "=== GOAL: Propose+Critique ==="
        )
        logger.info(
            "Goal: real proposer call -> real critic call (2 rounds: blind + with rationale), "
            "two separate Groq providers for independence guard. "
            "Expected rule: predicate_1=USES, predicate_2=GENERATES, status in {CRITIQUED,REJECTED}, "
            "proposer_model and critic_model non-null, proposer_rationale and critic_rationale non-empty, "
            "human_approved=False. "
            "Critic verdict may be APPROVE, REJECT, or REVISE — all valid."
        )
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

        ephemeral_db.add_all(
            [
                Claim(subject_id=a.id, predicate="USES", object_entity_id=b.id),
                Claim(subject_id=b.id, predicate="GENERATES", object_entity_id=c.id),
            ]
        )
        ephemeral_db.commit()

        # Two separate providers for independence guard
        with Session(settings_engine) as s:
            provider_a = _register_groq_provider(s, "groq-proposer")
            provider_b = _register_groq_provider(s, "groq-critic")
            _register_route(s, "Rule Proposer", provider_a.id)
            _register_route(s, "Rule Critic", provider_b.id)

        svc = InferenceRuleService()
        rule = await svc.propose_and_critique("USES", "GENERATES", run_id="full-cycle-groq")

        assert rule.id is not None
        assert rule.predicate_1 == "USES"
        assert rule.predicate_2 == "GENERATES"
        assert rule.status in {"CRITIQUED", "REJECTED"}
        assert rule.proposer_model is not None
        assert rule.critic_model is not None
        assert rule.proposer_rationale
        assert rule.critic_rationale
        assert rule.human_approved is False
        print(
            f"\n[groq-cycle] proposer={rule.proposer_model} critic={rule.critic_model} "
            f"implied_predicate={rule.implied_predicate!r} "
            f"verdict={rule.critic_verdict!r} status={rule.status}"
        )

    async def test_full_pipeline_propose_approve_materialize(self, ephemeral_db):
        logger.info(
            "=== GOAL: Full Pipeline (propose -> approve -> materialize) ==="
        )
        logger.info(
            "Goal: propose POWERS->EMITS, human-approve the rule (regardless of critic verdict), "
            "materialize InferredClaims. Single provider for both proposer and critic — "
            "exercises independence-guard warning path (no alternative to exclude). "
            "Expected: rule status=APPROVED after approve_rule(), human_approved=True, "
            "InferredClaim from Reactor to Waste Heat with predicate matching implied_predicate, "
            "non-empty path from get_inferred_claim_paths(). "
            "Skips if model REJECTs or implied_predicate is empty."
        )
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

        ephemeral_db.add_all(
            [
                Claim(subject_id=a.id, predicate="POWERS", object_entity_id=b.id),
                Claim(subject_id=b.id, predicate="EMITS", object_entity_id=c.id),
            ]
        )
        ephemeral_db.commit()

        with Session(settings_engine) as s:
            provider = _register_groq_provider(s, "groq-single")
            _register_route(s, "Rule Proposer", provider.id)
            _register_route(s, "Rule Critic", provider.id)

        rule_svc = InferenceRuleService()
        rule = await rule_svc.propose_and_critique(
            "POWERS", "EMITS", run_id="full-pipeline-groq"
        )

        if rule.status == "REJECTED":
            pytest.skip(
                f"Real model rejected this composition "
                f"(critic_rationale={rule.critic_rationale!r}); "
                "nothing to materialize. Rerun or adjust the example pair "
                "if consistently rejected."
            )

        approved = rule_svc.approve_rule(rule.id)
        assert approved.human_approved is True
        assert approved.status == "APPROVED"

        if not approved.implied_predicate:
            pytest.skip(
                "Real model produced empty implied_predicate "
                "(malformed JSON); nothing to materialize."
            )

        engine_svc = InferenceEngineService(session=ephemeral_db)
        created = engine_svc.materialize_inferred_claims()

        matching = [
            ic for ic in created if ic.subject_id == a.id and ic.object_id == c.id
        ]
        assert len(matching) == 1, (
            f"Expected exactly one InferredClaim from Reactor to Waste Heat via rule "
            f"'{approved.implied_predicate}', got: "
            f"{[(ic.subject_id, ic.predicate, ic.object_id) for ic in created]}"
        )
        ic = matching[0]
        assert ic.predicate == approved.implied_predicate
        repo = InferenceRepository(ephemeral_db)
        assert len(repo.get_inferred_claim_paths(ic.id)) > 0
        print(
            f"\n[groq-pipeline] materialized: Reactor --{ic.predicate}--> Waste Heat "
            f"(rule implied_predicate={approved.implied_predicate!r})"
        )

    async def test_candidate_discovery_against_real_data(self, ephemeral_db):
        logger.info(
            "=== GOAL: Candidate Discovery + Bulk Propose ==="
        )
        logger.info(
            "Goal: seed 6 entities with 6 claims forming 2-hop chains "
            "(USES->GENERATES x3, GENERATES->USES x3), "
            "call run_rule_proposal_pass() to auto-discover frequent predicate pairs "
            "and propose+critique each. "
            "Expected: >=1 InferenceRule with status in {CRITIQUED,REJECTED}, "
            "human_approved=False. "
            "Exercises: frequent_predicate_pairs SQL, "
            "example_chains construction from real claims, "
            "full propose+critique loop per candidate, "
            "rate-limit retry (1 retry with 15s backoff on exhausted errors)."
        )
        u = Universe(name="TEST_Discovery", is_explored=True)
        ephemeral_db.add(u)
        ephemeral_db.commit()
        ephemeral_db.refresh(u)

        entities = [
            Entity(name=f"E{i}", entity_type="X", universe_id=u.id)
            for i in range(6)
        ]
        ephemeral_db.add_all(entities)
        ephemeral_db.commit()
        for e in entities:
            ephemeral_db.refresh(e)

        pairs = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]
        claims = []
        for i, (s, o) in enumerate(pairs):
            predicate = "USES" if i % 2 == 0 else "GENERATES"
            claims.append(
                Claim(
                    subject_id=entities[s].id,
                    predicate=predicate,
                    object_entity_id=entities[o].id,
                )
            )
        ephemeral_db.add_all(claims)
        ephemeral_db.commit()

        with Session(settings_engine) as s:
            provider = _register_groq_provider(s, "groq-discovery")
            _register_route(s, "Rule Proposer", provider.id)
            _register_route(s, "Rule Critic", provider.id)

        svc = InferenceRuleService()
        results = None
        for attempt in range(2):
            try:
                results = await svc.run_rule_proposal_pass(run_id="discovery-groq")
                break
            except RuntimeError as e:
                if attempt == 0 and "exhausted" in str(e):
                    await asyncio.sleep(15)
                    continue
                raise
        assert results is not None

        assert len(results) >= 1
        for rule in results:
            assert rule.status in {"CRITIQUED", "REJECTED"}
            assert rule.human_approved is False
