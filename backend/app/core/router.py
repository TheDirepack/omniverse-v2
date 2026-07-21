import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import litellm
from sqlmodel import Session, select

from app.core.agent_event_types import AgentEventType
from app.core.agent_logger import agent_logger
from app.db.operational_session import operational_engine
from app.db.schema import (
    AgentRouteFallback,
    CandidateHealth,
    ExecutionState,
    ProviderConfig,
    ProviderKey,
)
from app.db.session import engine
from app.db.settings_session import settings_engine


def calculate_candidate_hash(provider_id: int, key_id: int | None, model: str) -> str:
    payload = f"{provider_id}:{key_id}:{model}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _clean_error(e: Exception) -> str:
    msg = str(e).split("\n")[0]
    if " - {" in msg:
        msg = msg.split(" - {")[0]
    msg = re.sub(r"^(litellm\.\w+Error: )+", r"\1", msg)
    return msg.strip()


class ModelRouter:
    def __init__(self):
        pass

    def _get_health(
        self, session: Session, provider_id: int, key_id: int | None, model: str
    ) -> CandidateHealth:
        c_hash = calculate_candidate_hash(provider_id, key_id, model)
        health = session.get(CandidateHealth, c_hash)
        if not health:
            health = CandidateHealth(
                candidate_hash=c_hash,
                provider_id=provider_id,
                key_id=key_id,
                model=model,
                failure_count=0,
            )
            session.add(health)
            session.commit()
            session.refresh(health)
        return health

    def _report_failure(
        self, session: Session, provider_id: int, key_id: int | None, model: str
    ):
        now = datetime.now(timezone.utc)

        # 1. Get health
        health = self._get_health(session, provider_id, key_id, model)

        # 2. Decay check
        if (
            health.last_failure_at
            and (now - health.last_failure_at).total_seconds() > 3600
        ):
            health.failure_count = max(0, health.failure_count - 1)

        # 3. Update
        # If the disability window expired, reset the failure counter
        if health.disabled_until and now > health.disabled_until:
            health.failure_count = 0
            health.disabled_until = None

        health.failure_count += 1
        health.last_failure_at = now

        # 4. Threshold check
        if health.failure_count >= 5:
            if not health.disabled_until or now > health.disabled_until:
                # Use atomic update to avoid race conditions when checking vs. setting
                session.execute(
                    select(CandidateHealth)
                    .where(
                        CandidateHealth.id == health.id,
                        CandidateHealth.disabled_until.is_(None) |
                        (CandidateHealth.disabled_until <= now)
                    )
                    .update({"disabled_until": now + timedelta(hours=4)})
                )
                session.flush()
                # Refresh health object to get updated timestamp
                session.refresh(health)

        session.add(health)
        session.commit()

    def _report_success(
        self, session: Session, provider_id: int, key_id: int | None, model: str
    ):
        health = self._get_health(session, provider_id, key_id, model)
        health.failure_count = 0
        health.disabled_until = None
        session.add(health)
        session.commit()

    async def run_model(
        self,
        task: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        run_id: str | None = None,
        **kwargs,
    ):
        """
        High-level entry point for model calls.
        Returns (response, model_name, key_id).
        """
        return await self.call_llm_with_tools(
            task, messages, tools or [], run_id=run_id, **kwargs
        )

    async def call_llm(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        run_id: str | None = None,
        **kwargs,
    ):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self.run_model(task, messages, tools=[], run_id=run_id, **kwargs)

    async def call_llm_with_tools(
        self,
        task: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        run_id: str | None = None,
        provider_id: int | None = None,
        exclude_provider_id: int | None = None,
        **kwargs,
    ):
        with Session(settings_engine) as session:
            # 1. Try to get routes for this specific task sorted by priority
            routes = session.exec(
                select(AgentRouteFallback)
                .where(AgentRouteFallback.task_type == task)
                .order_by(AgentRouteFallback.priority)
            ).all()
            print(f"[ModelRouter] Routes for task '{task}': {[r.task_type for r in routes]}")

            # If a specific provider was requested, restrict the fallback chain to
            # routes pointing at that provider (falling back to all routes if none match,
            # so an invalid/unknown provider_id doesn't hard-fail the whole call).
            if provider_id is not None:
                filtered = [r for r in routes if r.provider_id == provider_id]
                if filtered:
                    routes = filtered

            # 2. Fallback to "DEFAULT" routes if no specific route is configured for this task
            if not routes:
                routes = session.exec(
                    select(AgentRouteFallback)
                    .where(AgentRouteFallback.task_type == "DEFAULT")
                    .order_by(AgentRouteFallback.priority)
                ).all()
                if provider_id is not None:
                    filtered = [r for r in routes if r.provider_id == provider_id]
                    if filtered:
                        routes = filtered

            if not routes:
                raise ValueError(
                    f"No routing configured for task '{task}' and no DEFAULT route found."
                )

            # Independence guard: if a provider is explicitly excluded (e.g. the
            # Rule Critic must not reuse the Rule Proposer's provider for a given
            # run), drop routes pointing at it — but only if alternatives exist.
            # Falling back to the excluded provider when nothing else is
            # configured is allowed, but must be logged loudly since it silently
            # breaks the independence assumption callers rely on.
            if exclude_provider_id is not None:
                non_excluded = [
                    r for r in routes if r.provider_id != exclude_provider_id
                ]
                if non_excluded:
                    routes = non_excluded
                else:
                    print(
                        f"[ModelRouter] WARNING: no alternative provider configured for task '{task}' "
                        f"other than excluded provider {exclude_provider_id}. Independence guard could not be honored."
                    )
                    if run_id:
                        with Session(engine) as log_session:
                            log_session.add(
                                ExecutionState(
                                    run_id=run_id,
                                    node_name="ModelRouter",
                                    thought=f"WARNING: independence guard failed for task '{task}' — no non-excluded provider available, reusing provider {exclude_provider_id}.",
                                    status="WARNING",
                                    state_snapshot="{}",
                                )
                            )
                            log_session.commit()

            # Collect all candidate configurations first
            candidates = []
            for route in routes:
                provider = (
                    session.get(ProviderConfig, route.provider_id)
                    if route.provider_id
                    else None
                )
                if not provider or not provider.provider_type:
                    continue

                keys = session.exec(
                    select(ProviderKey)
                    .where(ProviderKey.provider_id == provider.id)
                    .order_by(ProviderKey.priority)
                ).all()
                if not keys and provider.provider_type in {"ollama", "custom"}:
                    keys = [ProviderKey(id=-1, api_key="not-needed", priority=0)]

                models = [
                    m.strip()
                    for m in (route.models or provider.models or "").split(",")
                    if m.strip()
                ]

                for key in keys:
                    for model in models:
                        model_prefix = (
                            "openai"
                            if provider.provider_type == "custom"
                            else provider.provider_type
                        )
                        candidates.append(
                            {
                                "provider": provider,
                                "key": key,
                                "model": model,
                                "full_model": f"{model_prefix}/{model}",
                            }
                        )

            for candidate in candidates:
                # Check if candidate is disabled
                with Session(operational_engine) as health_session:
                    health = self._get_health(
                        health_session,
                        candidate["provider"].id,
                        candidate["key"].id if candidate["key"].id != -1 else None,
                        candidate["model"],
                    )
                    if (
                        health.disabled_until
                        and health.disabled_until > datetime.now(timezone.utc)
                    ):
                        continue

                try:
                    full_model = candidate["full_model"]
                    response = await litellm.acompletion(
                        model=full_model,
                        messages=messages,
                        tools=tools or None,
                        tool_choice="auto" if tools else None,
                        api_key=candidate["key"].api_key,
                        api_base=candidate["provider"].base_url,
                        **kwargs,
                    )

                    # Report success
                    with Session(operational_engine) as health_session:
                        self._report_success(
                            health_session,
                            candidate["provider"].id,
                            candidate["key"].id if candidate["key"].id != -1 else None,
                            candidate["model"],
                        )

                    # Log agent model call
                    agent_logger.log(
                        agent="ModelRouter",
                        event_type=AgentEventType.MODEL_CALL,
                        content=f"Successful response from {candidate['full_model']}",
                        model=candidate["full_model"],
                        key_id=str(candidate["key"].id),
                    )

                    if run_id:
                        from app.services.execution_service import ExecutionService

                        with Session(engine) as exec_session:
                            exec_service = ExecutionService(session=exec_session)

                            # Calculate usage
                            usage = (
                                response.usage.total_tokens
                                if hasattr(response, "usage") and response.usage
                                else 0
                            )

                            exec_service.log_transition(
                                run_id=run_id,
                                node_name="ModelRouter",
                                thought=f"Success: Candidate {candidate['full_model']} provided a response.",
                                status="INFO",
                                state={},
                                token_usage=usage,
                            )
                    return response, candidate["full_model"], str(candidate["key"].id)
                except Exception as e:
                    # Programming errors should NOT be reported as provider failures.
                    if not isinstance(
                        e,
                        (
                            litellm.APIError,
                            litellm.AuthenticationError,
                            litellm.APIConnectionError,
                            litellm.RateLimitError,
                            litellm.ServiceUnavailableError,
                        ),
                    ):
                        agent_logger.log(
                            agent="ModelRouter",
                            event_type=AgentEventType.ERROR,
                            content=f"Programming/Logic error in {candidate['full_model']}: {e!s}",
                            model=candidate["full_model"],
                            key_id=str(candidate["key"].id),
                        )
                        raise

                    # Report failure
                    with Session(operational_engine) as health_session:
                        self._report_failure(
                            health_session,
                            candidate["provider"].id,
                            candidate["key"].id if candidate["key"].id != -1 else None,
                            candidate["model"],
                        )

                    clean_e = _clean_error(e)
                    agent_logger.log(
                        agent="ModelRouter",
                        event_type=AgentEventType.ERROR,
                        content=f"Fallback: {candidate['full_model']} failed due to {clean_e}. Trying next candidate.",
                        model=candidate["full_model"],
                        key_id=str(candidate["key"].id),
                    )

                    if run_id:
                        with Session(engine) as log_session:
                            log_entry = ExecutionState(
                                run_id=run_id,
                                node_name="ModelRouter",
                                thought=f"Fallback: {candidate['full_model']} failed due to {clean_e}. Trying next candidate.",
                                status="INFO",
                                state_snapshot="{}",
                            )
                            log_session.add(log_entry)
                            log_session.commit()
                    print(
                        f"[ModelRouter] Fallback failed for {candidate['full_model']} with key {candidate['key'].id}: {clean_e}"
                    )
                    continue

            raise RuntimeError(f"All fallback options exhausted for task '{task}'.")

    def list_provider_models(self, provider_id: int) -> list[str]:
        with Session(settings_engine) as session:
            provider = session.get(ProviderConfig, provider_id)
            if not provider or not provider.models:
                return []
            return [
                model.strip() for model in provider.models.split(",") if model.strip()
            ]


router = ModelRouter()
