import json
import logging
from collections.abc import Sequence

from sqlmodel import Session, select

from app.agents.agent_names import (
    AGENT_NAMES,  # noqa: F401 (ensures names are registered)
)
from app.agents.prompt_templates import RULE_CRITIC_SYSTEM, RULE_PROPOSER_SYSTEM
from app.core.router import router as model_router
from app.db.schema import AgentRouteFallback, InferenceRule
from app.db.session import engine
from app.repositories.inference import InferenceRepository

logger = logging.getLogger(__name__)

RULE_PROPOSER_TASK = "Rule Proposer"
RULE_CRITIC_TASK = "Rule Critic"

MIN_PAIR_OCCURRENCES = 3
MAX_EXAMPLES_SHOWN = 5


def _safe_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json")
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text)
    except json.JSONDecodeError:
        return {}
    else:
        return obj


class InferenceRuleService:
    def __init__(self, session: Session | None = None):
        # Do NOT open a session here — matches the fix in 5f45596, which
        # removed exactly this eager-session pattern from every other
        # service. Each method below opens (or reuses an injected) session
        # scoped to just that call.
        self.session = session

    # --- Candidate discovery ---
    # Note: this operates purely on Claim.predicate strings, which are
    # whatever vocabulary the research/extraction stage produced for THAT
    # universe. Nothing here assumes BattleTech, Halo, LOTR, or any specific
    # setting — a rule proposed from Halo's "WIELDS"/"POWERED_BY" pattern and
    # one proposed from BattleTech's "USES"/"GENERATES" pattern are just two
    # different rows in the same table, evaluated identically.

    def find_candidate_pairs(self) -> list[tuple]:
        session = self.session or Session(engine)
        try:
            repo = InferenceRepository(session)
            pairs = repo.frequent_predicate_pairs(min_count=MIN_PAIR_OCCURRENCES)
            return [
                (p1, p2, cnt)
                for (p1, p2, cnt) in pairs
                if repo.existing_rule_for_pair(p1, p2) is None
            ]
        finally:
            if not self.session:
                session.close()

    def _example_chains(
        self,
        session: Session,
        predicate_1: str,
        predicate_2: str,
        limit: int = MAX_EXAMPLES_SHOWN,
    ) -> list[dict]:
        repo = InferenceRepository(session)
        first_hop = repo.get_claims_by_predicate(predicate_1)
        examples = []
        for c1 in first_hop:
            second_hops = repo.find_claims_with_subject_predicate(
                c1.object_entity_id, predicate_2
            )
            for c2 in second_hops:
                examples.append(
                    {
                        "subject_id": c1.subject_id,
                        "mid_id": c1.object_entity_id,
                        "object_id": c2.object_entity_id,
                    }
                )
                if len(examples) >= limit:
                    return examples
        return examples

    def _resolve_provider_id_for_task(self, session: Session, task: str) -> int | None:
        print(f"DEBUG: resolving provider for task {task}")
        # Best-effort: use the top-priority route's provider_id for this task,
        # falling back to DEFAULT. If none configured, returns None (no
        # exclusion possible; router logs when it can't honor the guard).
        route = session.exec(
            select(AgentRouteFallback)
            .where(AgentRouteFallback.task_type == task)
            .order_by(AgentRouteFallback.priority)
        ).first()
        if route:
            print(f"DEBUG: found route for {task}: provider_id={route.provider_id}")
        if not route:
            print(f"DEBUG: no route for {task}, falling back to DEFAULT")
            route = session.exec(
                select(AgentRouteFallback)
                .where(AgentRouteFallback.task_type == "DEFAULT")
                .order_by(AgentRouteFallback.priority)
            ).first()
            if route:
                print(f"DEBUG: found DEFAULT route: provider_id={route.provider_id}")
        return route.provider_id if route else None

    # --- Proposal + critique (manual trigger, per pair) ---

    async def propose_and_critique(
        self, predicate_1: str, predicate_2: str, run_id: str | None = None
    ) -> InferenceRule:
        session = self.session or Session(engine)
        try:
            examples = self._example_chains(session, predicate_1, predicate_2)
            proposer_provider_id = self._resolve_provider_id_for_task(
                session, RULE_PROPOSER_TASK
            )
        finally:
            if not self.session:
                session.close()

        proposer_prompt = (
            f"PREDICATE_1: {predicate_1}\nPREDICATE_2: {predicate_2}\n"
            f"EXAMPLE CHAINS (entity ids, resolve meaning from context if needed): "
            f"{json.dumps(examples)}\n"
            "These predicates are drawn from whatever fictional universe produced "
            "them - do not assume any specific setting (mecha, fantasy, sci-fi, "
            "etc). Judge the composition purely on the logical/causal "
            "relationship the predicate names imply, so the rule generalizes to "
            "any universe using this same predicate vocabulary.\n"
            "Propose whether subject--PREDICATE_1-->mid--PREDICATE_2-->object "
            "justifies a direct subject->object edge."
        )
        proposer_resp, proposer_model, _ = await model_router.call_llm(
            RULE_PROPOSER_TASK, RULE_PROPOSER_SYSTEM, proposer_prompt, run_id=run_id
        )
        proposer_raw = proposer_resp.choices[0].message.content
        logger.info("Proposer model=%s raw=%s", proposer_model, proposer_raw)
        proposal = _safe_json(proposer_raw)
        logger.info("Proposer parsed=%s", proposal)

        session = self.session or Session(engine)
        try:
            repo = InferenceRepository(session)
            rule = InferenceRule(
                predicate_1=predicate_1,
                predicate_2=predicate_2,
                implied_predicate=proposal.get("implied_predicate", ""),
                rule_type=proposal.get("rule_type", "compose"),
                status="PROPOSED",
                proposer_model=proposer_model,
                proposer_rationale=proposal.get("rationale", ""),
            )
            rule = repo.create_rule(rule)
            rule_id = rule.id
            implied_predicate = rule.implied_predicate
            rule_type = rule.rule_type
        finally:
            if not self.session:
                session.close()

        # Independence guard: critic call explicitly excludes the proposer's
        # resolved provider, enforced at the routing layer.
        critic_prompt_blind = (
            f"PREDICATE_1: {predicate_1}\nPREDICATE_2: {predicate_2}\n"
            f"Proposed implied_predicate: {implied_predicate}\nrule_type: {rule_type}\n"
            f"EXAMPLE CHAINS: {json.dumps(examples)}\n"
            "These predicates come from an unspecified fictional universe - judge the "
            "composition generically, not against any specific setting's lore.\n"
            "Give your independent verdict before seeing any rationale."
        )
        critic_resp_1, critic_model, _ = await model_router.call_llm(
            RULE_CRITIC_TASK,
            RULE_CRITIC_SYSTEM,
            critic_prompt_blind,
            run_id=run_id,
            exclude_provider_id=proposer_provider_id,
        )
        critic_raw = critic_resp_1.choices[0].message.content
        logger.info("Critic-blind model=%s raw=%s", critic_model, critic_raw)
        blind_verdict = _safe_json(critic_raw)
        logger.info("Critic-blind parsed=%s", blind_verdict)

        critic_prompt_final = (
            critic_prompt_blind
            + f"\n\nYour independent verdict was: {json.dumps(blind_verdict)}\n"
            + f"Proposer's rationale (seen only now): {proposal.get('rationale', '')}\n"
            "Does this change your verdict? Give your FINAL verdict."
        )
        critic_resp_2, critic_model_2, _ = await model_router.call_llm(
            RULE_CRITIC_TASK,
            RULE_CRITIC_SYSTEM,
            critic_prompt_final,
            run_id=run_id,
            exclude_provider_id=proposer_provider_id,
        )
        critic_final_raw = critic_resp_2.choices[0].message.content
        logger.info("Critic-final model=%s raw=%s", critic_model_2, critic_final_raw)
        final_verdict = _safe_json(critic_final_raw)
        logger.info("Critic-final parsed=%s", final_verdict)

        session = self.session or Session(engine)
        try:
            repo = InferenceRepository(session)
            assert rule_id is not None
            rule = repo.get_rule(rule_id)
            if not rule:
                raise RuntimeError(
                    f"Rule {rule_id} not found in database."
                )
            rule.critic_model = critic_model
            rule.critic_verdict = final_verdict.get("verdict")
            rule.critic_rationale = final_verdict.get("rationale")
            if final_verdict.get("verdict") == "REVISE":
                if final_verdict.get("revised_implied_predicate"):
                    rule.implied_predicate = final_verdict["revised_implied_predicate"]
                if final_verdict.get("revised_rule_type"):
                    rule.rule_type = final_verdict["revised_rule_type"]
            rule.status = (
                "CRITIQUED" if final_verdict.get("verdict") != "REJECT" else "REJECTED"
            )
            return repo.update_rule(rule)
        finally:
            if not self.session:
                session.close()

    # --- Manual-trigger entrypoint ---

    async def run_rule_proposal_pass(
        self, run_id: str | None = None
    ) -> list[InferenceRule]:
        """The button-press entrypoint: scans for candidate predicate pairs
        (generic across any universe's predicate vocabulary) and runs the
        proposer/critic loop for each. Never runs automatically."""
        candidates = self.find_candidate_pairs()
        results = []
        for predicate_1, predicate_2, _count in candidates:
            rule = await self.propose_and_critique(
                predicate_1, predicate_2, run_id=run_id
            )
            results.append(rule)
        # Each propose_and_critique call uses its own short-lived session, so
        # every returned rule is already detached but fully loaded (its own
        # session's final refresh+return happened before that session
        # closed) -- unlike materialize_inferred_claims, there's no shared
        # session here to expire earlier rows, so no extra refresh needed.
        return results

    # --- Human approval ---

    def approve_rule(self, rule_id: int) -> InferenceRule | None:
        session = self.session or Session(engine)
        try:
            repo = InferenceRepository(session)
            rule = repo.get_rule(rule_id)
            if not rule:
                return None
            rule.human_approved = True
            rule.status = "APPROVED"
            return repo.update_rule(rule)
        finally:
            if not self.session:
                session.close()

    def reject_rule(self, rule_id: int) -> InferenceRule | None:
        session = self.session or Session(engine)
        try:
            repo = InferenceRepository(session)
            rule = repo.get_rule(rule_id)
            if not rule:
                return None
            rule.human_approved = False
            rule.status = "REJECTED"
            return repo.update_rule(rule)
        finally:
            if not self.session:
                session.close()

    def get_rules_by_status(self, status: str) -> Sequence[InferenceRule]:
        session = self.session or Session(engine)
        try:
            return InferenceRepository(session).get_rules_by_status(status)
        finally:
            if not self.session:
                session.close()
