import json
from typing import List, Optional, Sequence
from sqlmodel import Session, select
from app.db.session import engine
from app.db.schema import InferenceRule, AgentRouteFallback
from app.repositories.inference import InferenceRepository
from app.core.router import router as model_router
from app.agents.agent_names import AGENT_NAMES  # noqa: F401 (ensures names are registered)
from app.agents.prompt_templates import RULE_PROPOSER_SYSTEM, RULE_CRITIC_SYSTEM

RULE_PROPOSER_TASK = "Rule Proposer"
RULE_CRITIC_TASK = "Rule Critic"

MIN_PAIR_OCCURRENCES = 3
MAX_EXAMPLES_SHOWN = 5


def _safe_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


class InferenceRuleService:
    def __init__(self, session: Optional[Session] = None):
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

    def find_candidate_pairs(self) -> List[tuple]:
        with Session(engine) if not self.session else self.session as session:
            repo = InferenceRepository(session)
            pairs = repo.frequent_predicate_pairs(min_count=MIN_PAIR_OCCURRENCES)
            return [
                (p1, p2, cnt) for (p1, p2, cnt) in pairs
                if repo.existing_rule_for_pair(p1, p2) is None
            ]

    def _example_chains(self, session: Session, predicate_1: str, predicate_2: str, limit: int = MAX_EXAMPLES_SHOWN) -> List[dict]:
        repo = InferenceRepository(session)
        first_hop = repo.get_claims_by_predicate(predicate_1)
        examples = []
        for c1 in first_hop:
            second_hops = repo.find_claims_with_subject_predicate(c1.object_id, predicate_2)
            for c2 in second_hops:
                examples.append({
                    "subject_id": c1.subject_id,
                    "mid_id": c1.object_id,
                    "object_id": c2.object_id,
                })
                if len(examples) >= limit:
                    return examples
        return examples

    def _resolve_provider_id_for_task(self, session: Session, task: str) -> Optional[int]:
        # Best-effort: use the top-priority route's provider_id for this task,
        # falling back to DEFAULT. If none configured, returns None (no
        # exclusion possible; router logs when it can't honor the guard).
        route = session.exec(
            select(AgentRouteFallback).where(AgentRouteFallback.task_type == task).order_by(AgentRouteFallback.priority)
        ).first()
        if not route:
            route = session.exec(
                select(AgentRouteFallback).where(AgentRouteFallback.task_type == "DEFAULT").order_by(AgentRouteFallback.priority)
            ).first()
        return route.provider_id if route else None

    # --- Proposal + critique (manual trigger, per pair) ---

    async def propose_and_critique(self, predicate_1: str, predicate_2: str, run_id: Optional[str] = None) -> InferenceRule:
        with Session(engine) if not self.session else self.session as session:
            examples = self._example_chains(session, predicate_1, predicate_2)
            proposer_provider_id = self._resolve_provider_id_for_task(session, RULE_PROPOSER_TASK)

        proposer_prompt = (
            f"PREDICATE_1: {predicate_1}\nPREDICATE_2: {predicate_2}\n"
            f"EXAMPLE CHAINS (entity ids, resolve meaning from context if needed): {json.dumps(examples)}\n"
            "These predicates are drawn from whatever fictional universe produced them - "
            "do not assume any specific setting (mecha, fantasy, sci-fi, etc). Judge the "
            "composition purely on the logical/causal relationship the predicate names imply, "
            "so the rule generalizes to any universe using this same predicate vocabulary.\n"
            "Propose whether subject--PREDICATE_1-->mid--PREDICATE_2-->object justifies "
            "a direct subject->object edge."
        )
        proposer_resp, proposer_model, _ = await model_router.call_llm(
            RULE_PROPOSER_TASK, RULE_PROPOSER_SYSTEM, proposer_prompt, run_id=run_id
        )
        proposal = _safe_json(proposer_resp.choices[0].message.content)

        with Session(engine) if not self.session else self.session as session:
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
            RULE_CRITIC_TASK, RULE_CRITIC_SYSTEM, critic_prompt_blind,
            run_id=run_id, exclude_provider_id=proposer_provider_id
        )
        blind_verdict = _safe_json(critic_resp_1.choices[0].message.content)

        critic_prompt_final = (
            critic_prompt_blind
            + f"\n\nYour independent verdict was: {json.dumps(blind_verdict)}\n"
            + f"Proposer's rationale (seen only now): {proposal.get('rationale', '')}\n"
            "Does this change your verdict? Give your FINAL verdict."
        )
        critic_resp_2, _, _ = await model_router.call_llm(
            RULE_CRITIC_TASK, RULE_CRITIC_SYSTEM, critic_prompt_final,
            run_id=run_id, exclude_provider_id=proposer_provider_id
        )
        final_verdict = _safe_json(critic_resp_2.choices[0].message.content)

        with Session(engine) if not self.session else self.session as session:
            repo = InferenceRepository(session)
            rule = repo.get_rule(rule_id)
            rule.critic_model = critic_model
            rule.critic_verdict = final_verdict.get("verdict")
            rule.critic_rationale = final_verdict.get("rationale")
            if final_verdict.get("verdict") == "REVISE":
                if final_verdict.get("revised_implied_predicate"):
                    rule.implied_predicate = final_verdict["revised_implied_predicate"]
                if final_verdict.get("revised_rule_type"):
                    rule.rule_type = final_verdict["revised_rule_type"]
            rule.status = "CRITIQUED" if final_verdict.get("verdict") != "REJECT" else "REJECTED"
            return repo.update_rule(rule)

    # --- Manual-trigger entrypoint ---

    async def run_rule_proposal_pass(self, run_id: Optional[str] = None) -> List[InferenceRule]:
        """The button-press entrypoint: scans for candidate predicate pairs
        (generic across any universe's predicate vocabulary) and runs the
        proposer/critic loop for each. Never runs automatically."""
        candidates = self.find_candidate_pairs()
        results = []
        for predicate_1, predicate_2, _count in candidates:
            rule = await self.propose_and_critique(predicate_1, predicate_2, run_id=run_id)
            results.append(rule)
        # Each propose_and_critique call uses its own short-lived session, so
        # every returned rule is already detached but fully loaded (its own
        # session's final refresh+return happened before that session
        # closed) -- unlike materialize_inferred_claims, there's no shared
        # session here to expire earlier rows, so no extra refresh needed.
        return results

    # --- Human approval ---

    def approve_rule(self, rule_id: int) -> Optional[InferenceRule]:
        with Session(engine) if not self.session else self.session as session:
            repo = InferenceRepository(session)
            rule = repo.get_rule(rule_id)
            if not rule:
                return None
            rule.human_approved = True
            rule.status = "APPROVED"
            return repo.update_rule(rule)

    def reject_rule(self, rule_id: int) -> Optional[InferenceRule]:
        with Session(engine) if not self.session else self.session as session:
            repo = InferenceRepository(session)
            rule = repo.get_rule(rule_id)
            if not rule:
                return None
            rule.human_approved = False
            rule.status = "REJECTED"
            return repo.update_rule(rule)

    def get_rules_by_status(self, status: str) -> Sequence[InferenceRule]:
        with Session(engine) if not self.session else self.session as session:
            return InferenceRepository(session).get_rules_by_status(status)
